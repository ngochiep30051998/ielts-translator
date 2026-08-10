package com.hiepnn.ieltstranslator.quiz;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Endpoint giải thích đáp án. Gemini bị {@code @MockitoBean} chứ không phải WireMock —
 * đúng lối QuizControllerIT đang dùng; WireMock chỉ có chỗ khi thứ đang test là tầng HTTP.
 */
@AutoConfigureMockMvc
class QuizExplainIT extends AbstractPostgresIT {

    @Autowired MockMvc mockMvc;
    @Autowired VocabEntryRepository vocab;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    @MockitoBean GeminiClient geminiClient;

    @BeforeEach
    void clean() {
        reset(geminiClient);
        jdbc.update("DELETE FROM quiz_attempt");
        jdbc.update("DELETE FROM quiz_item");
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM srs_distractor");
        jdbc.update("DELETE FROM vocab_entry");
    }

    /** Một từ đã ôn ít nhất một lượt — điều kiện để lọt vào danh sách ứng viên. */
    private Long seedReviewedWord(String term, String meaningVi) {
        VocabEntry v = new VocabEntry();
        // user_id là NOT NULL từ V6 — dựng entry mà quên chủ sở hữu là nổ lúc insert.
        v.setUser(ownerUser());
        v.setTerm(term);
        v.setLemma(term);
        v.setLang("en");
        v.setPos("verb");
        v.setMeaningVi(meaningVi);
        v.setCollocations(objectMapper.createArrayNode());
        v.setExamples(objectMapper.createArrayNode());
        Long id = vocab.saveAndFlush(v).getId();
        jdbc.update("""
                INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses)
                VALUES (?, CURRENT_DATE, 'REVIEW', 3, 1)""", id);
        return id;
    }

    private long generateOne(String type) throws Exception {
        String body = mockMvc.perform(post("/api/quiz/generate").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"count\":5,\"type\":\"%s\"}".formatted(type)))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(body).get(0).get("id").asLong();
    }

    private void answer(long quizItemId, String answer) throws Exception {
        mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                Map.of("quizItemId", quizItemId, "answer", answer))))
                .andExpect(status().isOk());
    }

    private ResultActions explain(long quizItemId) throws Exception {
        return mockMvc.perform(post("/api/quiz/explain").header("Authorization", BEARER_OWNER)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"quizItemId\":%d}".formatted(quizItemId)));
    }

    /**
     * Đặt lại stub Gemini SAU khi đã nộp bài. Cần thiết vì chấm FREE_WRITE và giải thích
     * dùng chung GeminiTimeout.QUIZ_GRADE, nên không phân biệt được hai lượt bằng matcher.
     */
    private void stubExplain(String json) throws Exception {
        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE)))
                .thenReturn(objectMapper.readTree(json));
    }

    private void stubFillBlankGenerate(String sentence, String answer) throws Exception {
        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE)))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"mitigate","sentence":"%s","answer":"%s",
                  "hint":"làm nhẹ bớt"}]}""".formatted(sentence, answer)));
    }

    private void stubCollocationGenerate() throws Exception {
        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE)))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"mitigate",
                  "question":"Cụm nào đi với «mitigate» là tự nhiên?",
                  "options":["mitigate the risk","mitigate a cake","mitigate loudly",
                             "mitigate blue"],
                  "correct_index":0}]}"""));
    }

    /** Vị trí 0-based của một cụm trong options ĐÃ XÁO của item đang lưu. */
    private int indexOfOption(long quizItemId, String option) {
        String options = jdbc.queryForObject(
                "SELECT payload->>'options' FROM quiz_item WHERE id = ?", String.class,
                quizItemId);
        try {
            var array = objectMapper.readTree(options);
            for (int i = 0; i < array.size(); i++) {
                if (option.equals(array.get(i).asText())) {
                    return i;
                }
            }
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
        throw new IllegalStateException("Không tìm thấy lựa chọn: " + option);
    }

    /* ================= FILL_BLANK ================= */

    @Test
    @DisplayName("FILL_BLANK: sentenceEn là câu đề bài ĐÃ điền đáp án, ghép ở backend")
    void fillBlankSentenceIsFilledByBackend() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubFillBlankGenerate("Governments must ___ the impact of flooding.", "mitigate");
        long id = generateOne("FILL_BLANK");
        answer(id, "reduce");

        // Gemini CỐ Ý trả sentence_en rác: với loại này backend đã biết câu tiếng Anh nên
        // phải bỏ qua hoàn toàn chuỗi Gemini trả về.
        stubExplain("""
                {"explanation_vi":"\\"mitigate\\" đi với impact; \\"reduce\\" nhạt hơn.",
                 "answer_meaning_vi":"mitigate = giảm nhẹ",
                 "sentence_en":"CÂU RÁC GEMINI TỰ BỊA",
                 "sentence_vi":"Chính phủ phải giảm nhẹ tác động của lũ lụt."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn")
                        .value("Governments must mitigate the impact of flooding."))
                .andExpect(jsonPath("$.sentenceVi")
                        .value("Chính phủ phải giảm nhẹ tác động của lũ lụt."))
                .andExpect(jsonPath("$.answerMeaning").value("mitigate = giảm nhẹ"))
                .andExpect(jsonPath("$.explanation").value(containsString("reduce")));
    }

    @Test
    @DisplayName("FILL_BLANK bỏ qua câu vẫn giải thích được và vẫn đủ cặp câu")
    void skippedFillBlankStillExplained() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubFillBlankGenerate("Governments must ___ the impact of flooding.", "mitigate");
        long id = generateOne("FILL_BLANK");
        answer(id, "");

        stubExplain("""
                {"explanation_vi":"\\"mitigate\\" là làm nhẹ tác động tiêu cực.",
                 "answer_meaning_vi":"mitigate = giảm nhẹ",
                 "sentence_vi":"Chính phủ phải giảm nhẹ tác động của lũ lụt."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn")
                        .value("Governments must mitigate the impact of flooding."))
                .andExpect(jsonPath("$.sentenceVi")
                        .value("Chính phủ phải giảm nhẹ tác động của lũ lụt."));
    }

    /* ================= COLLOCATION_CHOICE ================= */

    @Test
    @DisplayName("COLLOCATION_CHOICE: sentenceEn lấy từ Gemini vì backend không có câu nào")
    void collocationSentenceComesFromGemini() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocationGenerate();
        long id = generateOne("COLLOCATION_CHOICE");
        answer(id, String.valueOf(indexOfOption(id, "mitigate a cake")));

        stubExplain("""
                {"explanation_vi":"«mitigate the risk» là cách người bản ngữ nói.",
                 "answer_meaning_vi":"mitigate the risk = giảm thiểu rủi ro",
                 "sentence_en":"Careful planning can mitigate the risk of flooding.",
                 "sentence_vi":"Quy hoạch cẩn thận có thể giảm thiểu rủi ro lũ lụt."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn")
                        .value("Careful planning can mitigate the risk of flooding."))
                .andExpect(jsonPath("$.sentenceVi")
                        .value("Quy hoạch cẩn thận có thể giảm thiểu rủi ro lũ lụt."))
                .andExpect(jsonPath("$.answerMeaning")
                        .value("mitigate the risk = giảm thiểu rủi ro"));
    }

    @Test
    @DisplayName("Prompt nhận NỘI DUNG cụm người học chọn, không phải index dạng chuỗi")
    void collocationPromptCarriesChosenOptionText() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocationGenerate();
        long id = generateOne("COLLOCATION_CHOICE");
        answer(id, String.valueOf(indexOfOption(id, "mitigate a cake")));

        stubExplain("""
                {"explanation_vi":"x","answer_meaning_vi":"y",
                 "sentence_en":"z","sentence_vi":"t"}""");
        explain(id).andExpect(status().isOk());

        // Đưa "2" vào prompt thì Gemini không có cách nào biết người học đã chọn gì, và
        // "chỉ thẳng chỗ sai" tụt về giải thích chung chung mà không ai phát hiện.
        ArgumentCaptor<String> prompt = ArgumentCaptor.forClass(String.class);
        verify(geminiClient).generateJson(prompt.capture(), any(),
                                          eq(GeminiTimeout.QUIZ_GRADE));
        assertThat(prompt.getValue()).contains("mitigate a cake");
        assertThat(prompt.getValue()).contains("mitigate the risk");
    }

    @Test
    @DisplayName("Bỏ qua câu chọn cụm: prompt nhận USER_ANSWER RỖNG, không phải cụm số 0")
    void skippedCollocationSendsEmptyUserAnswer() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocationGenerate();
        long id = generateOne("COLLOCATION_CHOICE");
        answer(id, "");

        stubExplain("""
                {"explanation_vi":"x","answer_meaning_vi":"y",
                 "sentence_en":"z","sentence_vi":"t"}""");
        explain(id).andExpect(status().isOk());

        // Chuỗi rỗng KHÔNG được hiểu thành index 0. Nếu optionAt trả về options.get(0)
        // thì prompt sẽ nói "bạn đã chọn «mitigate the risk»" với người vừa bỏ qua câu —
        // vừa sai sự thật, vừa đúng bằng đáp án.
        ArgumentCaptor<String> prompt = ArgumentCaptor.forClass(String.class);
        verify(geminiClient).generateJson(prompt.capture(), any(),
                                          eq(GeminiTimeout.QUIZ_GRADE));
        // Regex chứ không so chuỗi thẳng: dòng đó là "Người học đã chọn: {{USER_ANSWER}}",
        // có một dấu cách trước placeholder. Bất biến cần khẳng định là "không còn gì
        // ngoài khoảng trắng trên dòng đó", chứ không phải số dấu cách.
        assertThat(prompt.getValue()).containsPattern("Người học đã chọn:\\s*\\n");
    }

    /* ================= FREE_WRITE ================= */

    @Test
    @DisplayName("FREE_WRITE: sentenceEn là improvedVersion của lượt làm")
    void freeWriteSentenceIsImprovedVersion() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        long id = generateOne("FREE_WRITE");   // FREE_WRITE dựng thẳng, không gọi Gemini

        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE)))
                .thenReturn(objectMapper.readTree("""
                {"meaning_ok":true,"grammar_ok":true,"band_ok":true,"score":88,
                 "feedback_vi":"Câu dùng từ đúng nghĩa.",
                 "improved_version":"Governments must mitigate the impact of flooding."}"""));
        answer(id, "We mitigate it.");

        stubExplain("""
                {"explanation_vi":"\\"mitigate\\" đi với danh từ chỉ tác động tiêu cực.",
                 "answer_meaning_vi":"mitigate = giảm nhẹ",
                 "sentence_vi":"Chính phủ phải giảm nhẹ tác động của lũ lụt."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn")
                        .value("Governments must mitigate the impact of flooding."))
                .andExpect(jsonPath("$.sentenceVi")
                        .value("Chính phủ phải giảm nhẹ tác động của lũ lụt."));
    }

    @Test
    @DisplayName("FREE_WRITE không có improvedVersion thì sentenceEn là chính câu người học")
    void freeWriteFallsBackToUserSentence() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        long id = generateOne("FREE_WRITE");

        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE)))
                .thenReturn(objectMapper.readTree("""
                {"meaning_ok":true,"grammar_ok":true,"band_ok":true,"score":92,
                 "feedback_vi":"Câu đã tốt."}"""));
        answer(id, "We must mitigate the damage.");

        stubExplain("""
                {"explanation_vi":"Dùng đúng rồi.","answer_meaning_vi":"mitigate = giảm nhẹ",
                 "sentence_vi":"Chúng ta phải giảm nhẹ thiệt hại."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn").value("We must mitigate the damage."))
                .andExpect(jsonPath("$.sentenceVi").value("Chúng ta phải giảm nhẹ thiệt hại."));
    }

    @Test
    @DisplayName("FREE_WRITE bỏ qua câu: sentenceEn và sentenceVi CÙNG null")
    void skippedFreeWriteHasNoSentencePair() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        long id = generateOne("FREE_WRITE");
        answer(id, "");   // bỏ qua: QuizService không gọi Gemini để chấm

        stubExplain("""
                {"explanation_vi":"\\"mitigate\\" dùng với tác động tiêu cực.",
                 "answer_meaning_vi":"mitigate = giảm nhẹ","sentence_vi":""}""");

        String body = explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.explanation").value(containsString("mitigate")))
                .andReturn().getResponse().getContentAsString();

        // Khoá PHẢI có mặt với giá trị null: mirror TypeScript khai `string | null` chứ
        // không phải optional, hai bên chỉ khớp khi khoá luôn xuất hiện.
        var node = objectMapper.readTree(body);
        assertThat(node.has("sentenceEn")).isTrue();
        assertThat(node.get("sentenceEn").isNull()).isTrue();
        assertThat(node.get("sentenceVi").isNull()).isTrue();
    }

    /* ================= Chốt chặn ================= */

    @Test
    @DisplayName("Chưa trả lời thì 404 và KHÔNG gọi Gemini — không đọc trộm được đáp án")
    void explainBeforeAnsweringIsRejectedWithoutBurningQuota() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubFillBlankGenerate("Governments must ___ the impact.", "mitigate");
        long id = generateOne("FILL_BLANK");

        explain(id)
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"))
                .andExpect(jsonPath("$.retryable").value(false));

        // Không một call QUIZ_GRADE nào: vừa là chuyện quota, vừa là bằng chứng chốt chặn
        // nằm TRƯỚC lượt gọi Gemini chứ không phải sau.
        verify(geminiClient, never()).generateJson(anyString(), any(),
                                                   eq(GeminiTimeout.QUIZ_GRADE));
    }

    @Test
    @DisplayName("quizItemId không tồn tại → 404 NOT_FOUND")
    void unknownItemIsNotFound() throws Exception {
        explain(999999)
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"))
                .andExpect(jsonPath("$.retryable").value(false));
    }

    @Test
    @DisplayName("Gemini chết → GEMINI_UNAVAILABLE truyền nguyên, retry được")
    void geminiFailurePropagates() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubFillBlankGenerate("Governments must ___ the impact.", "mitigate");
        long id = generateOne("FILL_BLANK");
        answer(id, "reduce");

        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE)))
                .thenThrow(AppException.of(ErrorCode.GEMINI_UNAVAILABLE,
                        "Gemini đang không phản hồi"));

        explain(id)
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value("GEMINI_UNAVAILABLE"))
                .andExpect(jsonPath("$.retryable").value(true));
    }

    @Test
    @DisplayName("Gemini trả sentence_vi rỗng → bỏ CẢ CẶP, không trả một nửa")
    void halfSentencePairIsDroppedEntirely() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocationGenerate();
        long id = generateOne("COLLOCATION_CHOICE");
        answer(id, String.valueOf(indexOfOption(id, "mitigate the risk")));

        stubExplain("""
                {"explanation_vi":"Cụm này tự nhiên.","answer_meaning_vi":"= giảm rủi ro",
                 "sentence_en":"Careful planning can mitigate the risk.","sentence_vi":""}""");

        String body = explain(id)
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        // sentenceEn có giá trị thật nhưng thiếu bản dịch: giữ lại nó là bắt panel render
        // khối "Dịch câu" với đúng một dòng tiếng Anh và không có dịch.
        var node = objectMapper.readTree(body);
        assertThat(node.get("sentenceEn").isNull()).isTrue();
        assertThat(node.get("sentenceVi").isNull()).isTrue();
    }
}
