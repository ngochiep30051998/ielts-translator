package com.hiepnn.ieltstranslator.quiz;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

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

@AutoConfigureMockMvc
class QuizControllerIT extends AbstractPostgresIT {

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

    private String generate(String body) throws Exception {
        return mockMvc.perform(post("/api/quiz/generate").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
    }

    /* ---------- R2: đáp án không được lọt ra response ---------- */

    @Test
    @DisplayName("[R2] Response FILL_BLANK có term = null và KHÔNG chứa đáp án ở bất kỳ dạng nào")
    void fillBlankResponseNeverLeaksAnswer() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"mitigate",
                  "sentence":"Governments must ___ the impact of rising sea levels.",
                  "answer":"mitigated","hint":"làm cho nhẹ bớt"}]}"""));

        String body = generate("{\"count\":5,\"type\":\"FILL_BLANK\"}");

        String storedAnswer = jdbc.queryForObject(
                "SELECT payload->>'answer' FROM quiz_item", String.class);
        assertThat(storedAnswer).isEqualTo("mitigated");

        // So chuỗi JSON THÔ: đây là chỗ duy nhất bắt được ca "đáp án đi kèm dưới tên khác".
        assertThat(body).doesNotContain(storedAnswer);
        assertThat(body).doesNotContain("\"answer\"");
        assertThat(body).doesNotContain("correct_index");
        assertThat(body).doesNotContain("correctIndex");
        assertThat(body).contains("\"term\":null");

        JsonNode item = objectMapper.readTree(body).get(0);
        assertThat(item.get("term").isNull()).isTrue();
        assertThat(item.get("sentence").asText()).contains("___");
        assertThat(item.get("options").isNull()).isTrue();
        assertThat(item.get("question").asText()).contains("làm cho nhẹ bớt");
    }

    @Test
    @DisplayName("Hình dạng COLLOCATION_CHOICE: options đúng 4, sentence null, term có mặt")
    void collocationResponseShape() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocation();

        String body = generate("{\"count\":5,\"type\":\"COLLOCATION_CHOICE\"}");
        JsonNode item = objectMapper.readTree(body).get(0);

        assertThat(item.get("term").asText()).isEqualTo("mitigate");
        assertThat(item.get("sentence").isNull()).isTrue();
        assertThat(item.get("options")).hasSize(4);
        assertThat(body).doesNotContain("correct_index");
    }

    /* ---------- R1: index đáp án khớp đúng thứ tự options đã gửi ---------- */

    @Test
    @DisplayName("[R1] Index trong options nhận được chấm đúng; index lệch một chấm sai")
    void collocationIndexMatchesReturnedOptionOrder() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocation();

        String body = generate("{\"count\":5,\"type\":\"COLLOCATION_CHOICE\"}");
        JsonNode item = objectMapper.readTree(body).get(0);
        long quizItemId = item.get("id").asLong();

        int correctIndex = -1;
        for (int i = 0; i < item.get("options").size(); i++) {
            if ("mitigate the risk".equals(item.get("options").get(i).asText())) {
                correctIndex = i;
            }
        }
        assertThat(correctIndex).isNotNegative();

        mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":%d,\"answer\":\"%d\"}"
                                .formatted(quizItemId, correctIndex)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.correct").value(true))
                .andExpect(jsonPath("$.score").value(100));

        mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":%d,\"answer\":\"%d\"}"
                                .formatted(quizItemId, (correctIndex + 1) % 4)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.correct").value(false))
                .andExpect(jsonPath("$.score").value(0))
                .andExpect(jsonPath("$.feedback").value(containsString("mitigate the risk")));
    }

    @Test
    @DisplayName("[R1] Item lấy lại từ DB vẫn chấm đúng — thứ tự options sống sót qua JSONB")
    void collocationIndexStillMatchesAfterReuse() throws Exception {
        // Vì sao cần test riêng cho đường này: người dùng đi đường TÁI DÙNG nhiều hơn
        // đường sinh mới, mà mọi khẳng định R1 hiện có đều chấm trên đề vừa sinh trong
        // cùng một transaction. Đây là đường duy nhất mà thứ tự options phải sống sót
        // qua một vòng ghi/đọc JSONB thật.
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocation();

        String first = generate("{\"count\":5,\"type\":\"COLLOCATION_CHOICE\"}");
        JsonNode firstItem = objectMapper.readTree(first).get(0);

        // Lượt hai không được gọi Gemini: item chưa có attempt nào nên phải tái dùng.
        reset(geminiClient);
        String second = generate("{\"count\":5,\"type\":\"COLLOCATION_CHOICE\"}");
        verify(geminiClient, never()).generateJson(anyString(), any(), any());

        JsonNode reusedItem = objectMapper.readTree(second).get(0);
        assertThat(reusedItem.get("id").asLong()).isEqualTo(firstItem.get("id").asLong());
        assertThat(reusedItem.get("options")).isEqualTo(firstItem.get("options"));

        int correctIndex = -1;
        for (int i = 0; i < reusedItem.get("options").size(); i++) {
            if ("mitigate the risk".equals(reusedItem.get("options").get(i).asText())) {
                correctIndex = i;
            }
        }
        assertThat(correctIndex).isNotNegative();

        // Chấm theo index đọc từ response TÁI DÙNG — lệch thứ tự ở đây là chấm sai toàn
        // bộ câu trắc nghiệm mà không lỗi nào nổ ra.
        mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":%d,\"answer\":\"%d\"}"
                                .formatted(reusedItem.get("id").asLong(), correctIndex)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.correct").value(true))
                .andExpect(jsonPath("$.score").value(100));
    }

    /* ---------- R3: @AssertTrue thật sự chạy ---------- */

    @Test
    @DisplayName("[R3] Thiếu cả vocabIds lẫn count → 400 và message nêu ĐÍCH DANH hai field")
    void missingBothSelectorsIsBadRequest() throws Exception {
        mockMvc.perform(post("/api/quiz/generate").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"type\":\"FILL_BLANK\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INTERNAL"))
                .andExpect(jsonPath("$.retryable").value(false))
                // Chỉ assert status là xanh giả: @AssertTrue bị bỏ qua im lặng cũng ra 400
                // (từ chỗ khác), còn message rỗng. Hai containsString này mới là bằng chứng.
                .andExpect(jsonPath("$.message").value(containsString("vocabIds")))
                .andExpect(jsonPath("$.message").value(containsString("count")))
                // Bằng chứng @AssertTrue trên record sinh FIELD error chứ không phải global
                // error: handleValidation ghép "tên field + message", nên tên property
                // suy ra từ getter phải có mặt. Global error sẽ không có tiền tố này.
                .andExpect(jsonPath("$.message").value(containsString("exactlyOneSelector")));
    }

    @Test
    @DisplayName("Có CẢ HAI vocabIds và count → 400")
    void bothSelectorsIsBadRequest() throws Exception {
        mockMvc.perform(post("/api/quiz/generate").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"vocabIds\":[1],\"count\":5,\"type\":\"FILL_BLANK\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value(containsString("vocabIds")));
    }

    @Test
    @DisplayName("Thiếu type → 400")
    void missingTypeIsBadRequest() throws Exception {
        mockMvc.perform(post("/api/quiz/generate").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"count\":5}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value(containsString("type")));
    }

    @Test
    @DisplayName("count ngoài khoảng 1..50 và vocabIds rỗng đều là 400")
    void outOfRangeSelectorsAreBadRequest() throws Exception {
        mockMvc.perform(post("/api/quiz/generate").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"count\":51,\"type\":\"FILL_BLANK\"}"))
                .andExpect(status().isBadRequest());
        mockMvc.perform(post("/api/quiz/generate").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"vocabIds\":[],\"type\":\"FILL_BLANK\"}"))
                .andExpect(status().isBadRequest());
    }

    /* ---------- Nộp bài ---------- */

    @Test
    @DisplayName("quizItemId không tồn tại → 404 NOT_FOUND, không retry được")
    void unknownItemIsNotFound() throws Exception {
        mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":999999,\"answer\":\"x\"}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"))
                .andExpect(jsonPath("$.retryable").value(false));
    }

    @Test
    @DisplayName("[Q4] answer 1001 ký tự → 400 TEXT_TOO_LONG, message nêu con số 1000")
    void tooLongAnswerIsRejected() throws Exception {
        mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                java.util.Map.of("quizItemId", 1, "answer", "a".repeat(1001)))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("TEXT_TOO_LONG"))
                .andExpect(jsonPath("$.retryable").value(false))
                .andExpect(jsonPath("$.message").value(containsString("1000")));
    }

    @Test
    @DisplayName("[Q3] Chấm FREE_WRITE trả improvedVersion và lưu đúng chuỗi đó xuống DB")
    void freeWriteStoresImprovedVersion() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        String body = generate("{\"count\":5,\"type\":\"FREE_WRITE\"}");
        long quizItemId = objectMapper.readTree(body).get(0).get("id").asLong();

        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"meaning_ok":true,"grammar_ok":true,"band_ok":true,"score":88,
                 "feedback_vi":"Câu dùng từ đúng nghĩa.",
                 "improved_version":"Governments must mitigate the impact of flooding."}"""));

        mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":%d,\"answer\":\"We mitigate it.\"}"
                                .formatted(quizItemId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.correct").value(true))
                .andExpect(jsonPath("$.score").value(88))
                .andExpect(jsonPath("$.feedback").value("Câu dùng từ đúng nghĩa."))
                .andExpect(jsonPath("$.improvedVersion")
                        .value("Governments must mitigate the impact of flooding."));

        assertThat(jdbc.queryForObject(
                "SELECT improved_version FROM quiz_attempt", String.class))
                .isEqualTo("Governments must mitigate the impact of flooding.");
    }

    @Test
    @DisplayName("[Q3] Chấm FILL_BLANK để improvedVersion null ở cả response lẫn DB")
    void fillBlankHasNoImprovedVersion() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"mitigate","sentence":"They must ___ the impact.",
                  "answer":"mitigate","hint":"làm nhẹ bớt"}]}"""));
        String body = generate("{\"count\":5,\"type\":\"FILL_BLANK\"}");
        long quizItemId = objectMapper.readTree(body).get(0).get("id").asLong();

        String result = mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":%d,\"answer\":\"mitigate\"}"
                                .formatted(quizItemId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.correct").value(true))
                .andReturn().getResponse().getContentAsString();

        // Khoá PHẢI có mặt với giá trị null (không dùng @JsonInclude(NON_NULL)): mirror
        // TypeScript khai `string | null` chứ không phải optional, hai bên chỉ khớp khi
        // khoá luôn xuất hiện.
        JsonNode node = objectMapper.readTree(result);
        assertThat(node.has("improvedVersion")).isTrue();
        assertThat(node.get("improvedVersion").isNull()).isTrue();

        assertThat(jdbc.queryForObject(
                "SELECT improved_version FROM quiz_attempt", String.class)).isNull();
    }

    @Test
    @DisplayName("Trả lời sai FILL_BLANK thì feedback chứa luôn đáp án đúng")
    void wrongFillBlankFeedbackRevealsAnswer() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"mitigate","sentence":"They must ___ the impact.",
                  "answer":"mitigated","hint":"làm nhẹ bớt"}]}"""));
        String body = generate("{\"count\":5,\"type\":\"FILL_BLANK\"}");
        long quizItemId = objectMapper.readTree(body).get(0).get("id").asLong();

        mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":%d,\"answer\":\"mitigate\"}"
                                .formatted(quizItemId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.correct").value(false))
                .andExpect(jsonPath("$.feedback").value(containsString("mitigated")));
    }

    /* ---------- C1: bỏ qua câu là hành động học tập hợp lệ, không phải lỗi ---------- */

    @Test
    @DisplayName("[C1] Nộp answer rỗng cho FILL_BLANK → 200, chấm 0, VẪN ghi lịch sử làm bài")
    void blankAnswerIsSkippedNotRejectedFillBlank() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"mitigate","sentence":"They must ___ the impact.",
                  "answer":"mitigate","hint":"làm nhẹ bớt"}]}"""));
        long quizItemId = objectMapper.readTree(generate("{\"count\":5,\"type\":\"FILL_BLANK\"}"))
                .get(0).get("id").asLong();

        expectSkipped(quizItemId);

        // Điểm mấu chốt: có dòng quiz_attempt. Thiếu nó thì item vẫn nằm trong
        // findReusable và câu đã bỏ qua sẽ hiện lại ở đề sau như chưa từng làm.
        assertThat(jdbc.queryForObject("SELECT count(*) FROM quiz_attempt", Long.class))
                .isEqualTo(1L);
        assertThat(jdbc.queryForObject("SELECT user_answer FROM quiz_attempt", String.class))
                .isEmpty();
    }

    @Test
    @DisplayName("[C1] Nộp answer rỗng cho COLLOCATION_CHOICE → 200, chấm 0")
    void blankAnswerIsSkippedNotRejectedCollocation() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocation();
        long quizItemId = objectMapper
                .readTree(generate("{\"count\":5,\"type\":\"COLLOCATION_CHOICE\"}"))
                .get(0).get("id").asLong();

        expectSkipped(quizItemId);
    }

    @Test
    @DisplayName("[C1] Nộp answer rỗng cho FREE_WRITE → 200 và KHÔNG đốt một call Gemini nào")
    void blankAnswerSkipsGeminiForFreeWrite() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        long quizItemId = objectMapper.readTree(generate("{\"count\":5,\"type\":\"FREE_WRITE\"}"))
                .get(0).get("id").asLong();

        expectSkipped(quizItemId);

        // Chấm một bài viết rỗng là đốt quota để nhận về một lời chê hiển nhiên.
        org.mockito.Mockito.verify(geminiClient, never())
                .generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE));
    }

    private void expectSkipped(long quizItemId) throws Exception {
        mockMvc.perform(post("/api/quiz/answer").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":%d,\"answer\":\"\"}".formatted(quizItemId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.correct").value(false))
                .andExpect(jsonPath("$.score").value(0))
                .andExpect(jsonPath("$.feedback").value("Chưa trả lời."));
    }

    /* ---------- C2: body không đọc được là lỗi của request, không phải của server ---------- */

    @Test
    @DisplayName("[C2] type sai chính tả → 400, KHÔNG phải 500")
    void unknownEnumValueIsBadRequest() throws Exception {
        mockMvc.perform(post("/api/quiz/generate").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"count\":5,\"type\":\"FILLBLANK\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INTERNAL"))
                .andExpect(jsonPath("$.retryable").value(false))
                .andExpect(jsonPath("$.message").value(containsString("enum")));
    }

    @Test
    @DisplayName("[C2] JSON méo → 400, và message KHÔNG dội lại nội dung người dùng gửi")
    void malformedJsonIsBadRequest() throws Exception {
        String body = mockMvc.perform(post("/api/quiz/generate").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"count\":5,,,}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INTERNAL"))
                .andReturn().getResponse().getContentAsString();

        // Không đưa ex.getMessage() vào response: nó chứa nguyên đoạn JSON người dùng gửi
        // và cả tên class nội bộ.
        assertThat(body).doesNotContain("com.hiepnn").doesNotContain("JsonParseException");
    }

    private void stubCollocation() throws Exception {
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"mitigate",
                  "question":"Cụm nào đi với «mitigate» là tự nhiên?",
                  "options":["mitigate the risk","mitigate a cake","mitigate loudly",
                             "mitigate blue"],
                  "correct_index":0}]}"""));
    }
}
