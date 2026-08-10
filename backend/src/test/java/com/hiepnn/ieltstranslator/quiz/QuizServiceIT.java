package com.hiepnn.ieltstranslator.quiz;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
import com.hiepnn.ieltstranslator.quiz.dto.AnswerResultDto;
import com.hiepnn.ieltstranslator.quiz.dto.GenerateQuizRequest;
import com.hiepnn.ieltstranslator.quiz.dto.QuizItemDto;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class QuizServiceIT extends AbstractPostgresIT {

    @Autowired QuizService service;
    @Autowired QuizItemRepository items;
    @Autowired QuizAttemptRepository attempts;
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

    private Long saveWord(String term) {
        VocabEntry v = new VocabEntry();
        // user_id là NOT NULL từ V6 — dựng entry mà quên chủ sở hữu là nổ lúc insert.
        v.setUser(ownerUser());
        v.setTerm(term);
        v.setLemma(term);
        v.setLang("en");
        v.setPos("verb");
        v.setMeaningVi("nghĩa của " + term);
        v.setCollocations(objectMapper.createArrayNode());
        v.setExamples(objectMapper.createArrayNode());
        return vocab.saveAndFlush(v).getId();
    }

    private void card(Long vocabId, int repetitions, int lapses) {
        jdbc.update("""
                INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses)
                VALUES (?, CURRENT_DATE, 'REVIEW', ?, ?)""", vocabId, repetitions, lapses);
    }

    private void stubFillBlank(String... terms) throws Exception {
        String elements = java.util.Arrays.stream(terms)
                .map(t -> """
                        {"term":"%s","sentence":"They must ___ the risk.","answer":"%s","hint":"gợi ý"}"""
                        .formatted(t, t))
                .collect(Collectors.joining(","));
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("{\"items\":[" + elements + "]}"));
    }

    private GenerateQuizRequest byCount(int count, QuizType type) {
        return new GenerateQuizRequest(null, count, type);
    }

    /* ---------- Chọn ứng viên ---------- */

    @Test
    @DisplayName("Từ chưa ôn lần nào (repetitions = 0) không bị đưa vào đề")
    void excludesUnreviewedWords() throws Exception {
        Long reviewed = saveWord("reviewed");
        card(reviewed, 2, 0);
        Long fresh = saveWord("fresh");
        card(fresh, 0, 0);
        stubFillBlank("reviewed", "fresh");

        List<QuizItemDto> generated = service.generate(ownerId(), byCount(10, QuizType.FILL_BLANK));

        assertThat(generated).extracting(QuizItemDto::vocabEntryId).containsExactly(reviewed);
    }

    @Test
    @DisplayName("Ưu tiên từ ít bị hỏi nhất, cùng số lượt thì từ hay quên (lapses cao) trước")
    void prefersLeastQuizzedThenMostLapsed() throws Exception {
        Long lowLapses = saveWord("low");
        card(lowLapses, 3, 0);
        Long highLapses = saveWord("high");
        card(highLapses, 3, 9);
        stubFillBlank("high", "low");

        List<QuizItemDto> generated = service.generate(ownerId(), byCount(10, QuizType.FILL_BLANK));

        assertThat(generated).extracting(QuizItemDto::vocabEntryId)
                .containsExactly(highLapses, lowLapses);
    }

    @Test
    @DisplayName("Sổ chỉ có từ chưa ôn → mảng RỖNG, không gọi Gemini, không phải lỗi")
    void emptyWhenNoCandidates() {
        card(saveWord("fresh"), 0, 0);

        assertThat(service.generate(ownerId(), byCount(10, QuizType.FILL_BLANK))).isEmpty();
        verify(geminiClient, never())
                .generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE));
    }

    @Test
    @DisplayName("Sổ rỗng → mảng rỗng, không ném")
    void emptyWhenVocabBookIsEmpty() {
        assertThat(service.generate(ownerId(), byCount(10, QuizType.FILL_BLANK))).isEmpty();
    }

    @Test
    @DisplayName("vocabIds chỉ định thẳng thì bỏ qua điều kiện repetitions >= 1")
    void explicitVocabIdsIgnoreRepetitions() throws Exception {
        Long fresh = saveWord("fresh");
        card(fresh, 0, 0);
        stubFillBlank("fresh");

        List<QuizItemDto> generated = service.generate(ownerId(), 
                new GenerateQuizRequest(List.of(fresh), null, QuizType.FILL_BLANK));

        assertThat(generated).hasSize(1);
    }

    @Test
    @DisplayName("vocabIds toàn id không tồn tại → mảng rỗng, không gọi Gemini")
    void unknownVocabIdsGiveEmptyList() {
        assertThat(service.generate(ownerId(), 
                new GenerateQuizRequest(List.of(999_999L), null, QuizType.FILL_BLANK)))
                .isEmpty();
        verify(geminiClient, never()).generateJson(anyString(), any(), any());
    }

    @Test
    @DisplayName("[Q1] count = 10 nhưng chỉ có 4 ứng viên → trả đúng 4 item, không đệm thêm")
    void returnsFewerItemsThanRequestedWhenCandidatesRunOut() throws Exception {
        for (int i = 0; i < 4; i++) {
            card(saveWord("w" + i), 2, 0);
        }
        stubFillBlank("w0", "w1", "w2", "w3");

        assertThat(service.generate(ownerId(), byCount(10, QuizType.FILL_BLANK))).hasSize(4);
    }

    /* ---------- Đếm call Gemini ---------- */

    @Test
    @DisplayName("[R4] Sinh đề hai lần liên tiếp: lần hai tái dùng, 0 call Gemini thêm")
    void secondGenerateReusesWithoutCallingGemini() throws Exception {
        card(saveWord("w0"), 2, 0);
        stubFillBlank("w0");

        List<QuizItemDto> first = service.generate(ownerId(), byCount(5, QuizType.FILL_BLANK));
        List<QuizItemDto> second = service.generate(ownerId(), byCount(5, QuizType.FILL_BLANK));

        assertThat(second).extracting(QuizItemDto::id)
                .containsExactlyElementsOf(first.stream().map(QuizItemDto::id).toList());
        // eq(QUIZ_GENERATE) chứ không phải any(): mức TRANSLATE là của DistractorGenerator
        // chạy @Async, đếm lẫn vào đây là test đỏ ngẫu nhiên không tái hiện được.
        verify(geminiClient, times(1))
                .generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE));
    }

    @Test
    @DisplayName("Đổi prompt_version trong DB thì lần sinh sau phải gọi Gemini lại")
    void stalePromptVersionForcesRegeneration() throws Exception {
        card(saveWord("w0"), 2, 0);
        stubFillBlank("w0");

        service.generate(ownerId(), byCount(5, QuizType.FILL_BLANK));
        jdbc.update("UPDATE quiz_item SET prompt_version = 99");
        service.generate(ownerId(), byCount(5, QuizType.FILL_BLANK));

        verify(geminiClient, times(2))
                .generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE));
    }

    @Test
    @DisplayName("[Q1] FREE_WRITE tốn 0 call Gemini lúc sinh đề")
    void freeWriteCostsNothingToGenerate() {
        card(saveWord("w0"), 2, 0);

        assertThat(service.generate(ownerId(), byCount(5, QuizType.FREE_WRITE))).hasSize(1);
        verify(geminiClient, never()).generateJson(anyString(), any(), any());
    }

    @Test
    @DisplayName("Cả lô hỏng → PARSE_ERROR")
    void parseErrorWhenWholeBatchInvalid() throws Exception {
        card(saveWord("w0"), 2, 0);
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"w0","sentence":"Khong co cho trong.","answer":"w0","hint":"x"}]}"""));

        assertThatThrownBy(() -> service.generate(ownerId(), byCount(5, QuizType.FILL_BLANK)))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code())
                        .isEqualTo(ErrorCode.PARSE_ERROR));
    }

    /* ---------- Chấm bài ---------- */

    @Test
    @DisplayName("Chấm cùng một item hai lần ghi hai dòng lịch sử, không ghi đè")
    void answerRecordsNewAttemptEachTime() throws Exception {
        card(saveWord("w0"), 2, 0);
        stubFillBlank("w0");
        Long itemId = service.generate(ownerId(), byCount(5, QuizType.FILL_BLANK)).get(0).id();

        service.answer(ownerId(), itemId, "w0");
        service.answer(ownerId(), itemId, "sai rồi");

        assertThat(attempts.count()).isEqualTo(2L);
    }

    @Test
    @DisplayName("Chấm FREE_WRITE dùng đúng mức timeout QUIZ_GRADE")
    void freeWriteUsesGradeTimeout() throws Exception {
        card(saveWord("w0"), 2, 0);
        Long itemId = service.generate(ownerId(), byCount(5, QuizType.FREE_WRITE)).get(0).id();
        stubGrade(true, true, true, 80);

        service.answer(ownerId(), itemId, "I will w0 the risk.");

        verify(geminiClient, times(1))
                .generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE));
    }

    @Test
    @DisplayName("band_ok = false KHÔNG làm câu trả lời thành sai — nhãn band chỉ là tham khảo")
    void bandOkDoesNotDecideCorrect() throws Exception {
        card(saveWord("w0"), 2, 0);
        Long itemId = service.generate(ownerId(), byCount(5, QuizType.FREE_WRITE)).get(0).id();
        stubGrade(true, true, false, 70);

        AnswerResultDto result = service.answer(ownerId(), itemId, "I will w0 the risk.");

        assertThat(result.correct()).isTrue();
        assertThat(result.score()).isEqualTo(70);
    }

    @Test
    @DisplayName("meaning_ok = false thì sai, dù ngữ pháp đúng")
    void meaningFailureMakesAnswerWrong() throws Exception {
        card(saveWord("w0"), 2, 0);
        Long itemId = service.generate(ownerId(), byCount(5, QuizType.FREE_WRITE)).get(0).id();
        stubGrade(false, true, true, 30);

        assertThat(service.answer(ownerId(), itemId, "I ate a w0.").correct()).isFalse();
    }

    @Test
    @DisplayName("Điểm Gemini trả ngoài khoảng 0..100 bị kẹp lại, không lọt ra API")
    void scoreIsClamped() throws Exception {
        card(saveWord("w0"), 2, 0);
        Long itemId = service.generate(ownerId(), byCount(5, QuizType.FREE_WRITE)).get(0).id();
        stubGrade(true, true, true, 250);

        assertThat(service.answer(ownerId(), itemId, "I will w0 it.").score()).isEqualTo(100);
    }

    @Test
    @DisplayName("Answer không parse được thành index là TRẢ LỜI SAI, không phải lỗi")
    void garbageCollocationAnswerIsWrongNotError() throws Exception {
        card(saveWord("w0"), 2, 0);
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"w0","question":"Cụm nào tự nhiên?",
                  "options":["a","b","c","d"],"correct_index":1}]}"""));
        Long itemId = service.generate(ownerId(), byCount(5, QuizType.COLLOCATION_CHOICE)).get(0).id();

        AnswerResultDto result = service.answer(ownerId(), itemId, "hai");

        assertThat(result.correct()).isFalse();
        assertThat(result.score()).isZero();
        assertThat(result.feedback()).isNotBlank();
    }

    @Test
    @DisplayName("answer dài quá 1000 ký tự → TEXT_TOO_LONG, áp cho cả loại chấm local")
    void tooLongAnswerIsRejectedForEveryType() throws Exception {
        card(saveWord("w0"), 2, 0);
        stubFillBlank("w0");
        Long itemId = service.generate(ownerId(), byCount(5, QuizType.FILL_BLANK)).get(0).id();

        assertThatThrownBy(() -> service.answer(ownerId(), itemId, "a".repeat(1001)))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code())
                        .isEqualTo(ErrorCode.TEXT_TOO_LONG));
        assertThat(attempts.count()).isZero();
    }

    @Test
    @DisplayName("Item không tồn tại → NOT_FOUND")
    void unknownItemThrowsNotFound() {
        assertThatThrownBy(() -> service.answer(ownerId(), 123_456L, "x"))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code())
                        .isEqualTo(ErrorCode.NOT_FOUND));
    }

    @Test
    @DisplayName("Đề đã sinh vẫn nằm lại DB để lượt sau tái dùng")
    void generatedItemsArePersisted() throws Exception {
        card(saveWord("w0"), 2, 0);
        stubFillBlank("w0");

        service.generate(ownerId(), byCount(5, QuizType.FILL_BLANK));

        assertThat(items.count()).isEqualTo(1L);
    }

    private void stubGrade(boolean meaningOk, boolean grammarOk, boolean bandOk, int score)
            throws Exception {
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"meaning_ok":%s,"grammar_ok":%s,"band_ok":%s,"score":%d,
                 "feedback_vi":"Nhận xét tiếng Việt.",
                 "improved_version":"A better sentence."}"""
                        .formatted(meaningOk, grammarOk, bandOk, score)));
    }

    @Test
    @DisplayName("Mỗi từ trong lô sinh đúng một câu — 3 từ ra 3 câu, không nhân bản")
    void oneItemPerWord() throws Exception {
        IntStream.range(0, 3).forEach(i -> card(saveWord("w" + i), 2, 0));
        stubFillBlank("w0", "w1", "w2");

        assertThat(service.generate(ownerId(), byCount(3, QuizType.FILL_BLANK))).hasSize(3);
    }
}
