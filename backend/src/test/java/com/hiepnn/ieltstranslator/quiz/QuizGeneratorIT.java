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
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

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

class QuizGeneratorIT extends AbstractPostgresIT {

    @Autowired QuizGenerator generator;
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

    private List<Long> saveWords(int n) {
        List<Long> ids = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            VocabEntry v = new VocabEntry();
            // user_id là NOT NULL từ V6 — dựng entry mà quên chủ sở hữu là nổ lúc insert.
            v.setUser(ownerUser());
            v.setTerm("w" + i);
            v.setLemma("w" + i);
            v.setLang("en");
            v.setPos("verb");
            v.setMeaningVi("nghĩa của w" + i);
            v.setCollocations(objectMapper.createArrayNode());
            v.setExamples(objectMapper.createArrayNode());
            ids.add(vocab.saveAndFlush(v).getId());
        }
        return ids;
    }

    /** Lô fill-blank hợp lệ cho n từ w0..w(n-1). */
    private void stubFillBlank(int n) throws Exception {
        String elements = java.util.stream.IntStream.range(0, n)
                .mapToObj(i -> """
                        {"term":"w%d","sentence":"They must ___ the risk.","answer":"w%d","hint":"gợi ý %d"}"""
                        .formatted(i, i, i))
                .collect(Collectors.joining(","));
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("{\"items\":[" + elements + "]}"));
    }

    @Test
    @DisplayName("Một lô 6 từ FILL_BLANK tốn đúng MỘT call Gemini, không phải 6")
    void oneGeminiCallPerType() throws Exception {
        List<Long> ids = saveWords(6);
        stubFillBlank(6);

        List<QuizItem> built = generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK);

        assertThat(built).hasSize(6);
        verify(geminiClient, times(1))
                .generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE));
    }

    @Test
    @DisplayName("FREE_WRITE không tốn call Gemini nào lúc sinh đề — đề dựng từ chính sổ từ")
    void freeWriteCostsNoGeminiCall() {
        List<Long> ids = saveWords(3);

        List<QuizItem> built = generator.buildItems(ownerId(), ids, QuizType.FREE_WRITE);

        assertThat(built).hasSize(3);
        assertThat(built.get(0).getPayload().get("question").toString())
                .contains("w0", "nghĩa của w0");
        verify(geminiClient, never()).generateJson(anyString(), any(), any());
    }

    @Test
    @DisplayName("Lần sinh thứ hai tái dùng item chưa làm — 0 call Gemini thêm, cùng id item")
    void reusesUnattemptedItems() throws Exception {
        List<Long> ids = saveWords(3);
        stubFillBlank(3);

        List<Long> first = generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK)
                .stream().map(QuizItem::getId).toList();
        List<Long> second = generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK)
                .stream().map(QuizItem::getId).toList();

        assertThat(second).containsExactlyElementsOf(first);
        verify(geminiClient, times(1))
                .generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE));
        assertThat(items.count()).isEqualTo(3L);
    }

    @Test
    @DisplayName("Item đã có lượt làm thì không tái dùng — sinh đề mới")
    void doesNotReuseAfterAttempt() throws Exception {
        List<Long> ids = saveWords(1);
        stubFillBlank(1);

        QuizItem first = generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK).get(0);
        QuizAttempt attempt = new QuizAttempt();
        attempt.setQuizItem(first);
        attempt.setUserAnswer("w0");
        attempt.setCorrect(true);
        attempt.setScore(100);
        attempts.saveAndFlush(attempt);

        QuizItem second = generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK).get(0);

        assertThat(second.getId()).isNotEqualTo(first.getId());
        verify(geminiClient, times(2))
                .generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE));
    }

    @Test
    @DisplayName("Item sinh bằng prompt_version cũ thì bỏ, gọi Gemini sinh lại")
    void doesNotReuseStalePromptVersion() throws Exception {
        List<Long> ids = saveWords(1);
        stubFillBlank(1);

        QuizItem first = generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK).get(0);
        jdbc.update("UPDATE quiz_item SET prompt_version = 99 WHERE id = ?", first.getId());

        QuizItem second = generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK).get(0);

        assertThat(second.getId()).isNotEqualTo(first.getId());
        assertThat(second.getPromptVersion())
                .isEqualTo(generator.promptVersionFor(QuizType.FILL_BLANK));
        verify(geminiClient, times(2))
                .generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE));
    }

    @Test
    @DisplayName("Lô có item hỏng thì loại đúng item đó, phần còn lại vẫn dùng được")
    void dropsInvalidItemsKeepsRest() throws Exception {
        List<Long> ids = saveWords(3);
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[
                  {"term":"w0","sentence":"We must ___ it.","answer":"w0","hint":"x"},
                  {"term":"w1","sentence":"No blank here.","answer":"w1","hint":"x"},
                  {"term":"w2","sentence":"They ___ risk.","answer":"w2","hint":"x"}
                ]}"""));

        List<QuizItem> built = generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK);

        assertThat(built).hasSize(2);
        assertThat(items.count()).isEqualTo(2L);
    }

    @Test
    @DisplayName("Cả lô hỏng hết thì ném PARSE_ERROR — không trả đề rỗng giả vờ thành công")
    void throwsParseErrorWhenAllInvalid() throws Exception {
        List<Long> ids = saveWords(2);
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[
                  {"term":"w0","sentence":"No blank.","answer":"w0","hint":"x"},
                  {"term":"w1","sentence":"Also no blank.","answer":"w1","hint":"x"}
                ]}"""));

        assertThatThrownBy(() -> generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code())
                        .isEqualTo(ErrorCode.PARSE_ERROR));
    }

    @Test
    @DisplayName("Payload FILL_BLANK giữ đáp án và gợi ý để chấm bài sau này")
    void storesFillBlankPayload() throws Exception {
        List<Long> ids = saveWords(1);
        stubFillBlank(1);

        QuizItem item = generator.buildItems(ownerId(), ids, QuizType.FILL_BLANK).get(0);

        assertThat(item.getPayload())
                .containsEntry("answer", "w0")
                .containsKey("sentence")
                .containsKey("hint");
    }

    @Test
    @DisplayName("Options được xáo lúc lưu nhưng correct_index vẫn trỏ đúng đáp án đã xáo")
    void shufflesOptionsButKeepsCorrectIndexConsistent() throws Exception {
        List<Long> ids = saveWords(1);
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"w0","question":"Cụm nào tự nhiên?",
                  "options":["đúng","sai 1","sai 2","sai 3"],"correct_index":0}]}"""));

        QuizItem item = generator.buildItems(ownerId(), ids, QuizType.COLLOCATION_CHOICE).get(0);

        @SuppressWarnings("unchecked")
        List<String> options = (List<String>) item.getPayload().get("options");
        int correctIndex = ((Number) item.getPayload().get("correct_index")).intValue();
        assertThat(options).containsExactlyInAnyOrder("đúng", "sai 1", "sai 2", "sai 3");
        assertThat(options.get(correctIndex)).isEqualTo("đúng");
    }

    @Test
    @DisplayName("Xáo thật sự có xảy ra — 40 lần sinh không thể lần nào đáp án cũng ở vị trí 0")
    void actuallyShufflesAcrossManyItems() throws Exception {
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"w0","question":"Cụm nào tự nhiên?",
                  "options":["đúng","sai 1","sai 2","sai 3"],"correct_index":0}]}"""));

        List<Long> ids = saveWords(1);
        List<Integer> positions = new ArrayList<>();
        for (int i = 0; i < 40; i++) {
            // Xoá item cũ để lượt sau không rơi vào đường tái dùng.
            jdbc.update("DELETE FROM quiz_item");
            QuizItem item = generator.buildItems(ownerId(), ids, QuizType.COLLOCATION_CHOICE).get(0);
            positions.add(((Number) item.getPayload().get("correct_index")).intValue());
        }

        // Gemini có xu hướng đặt đáp án đúng ở vị trí 0; nếu backend không xáo thì cả 40
        // lần đều là 0 và quiz đoán được mà không cần biết từ. Xác suất dương tính giả
        // (xáo thật mà 40 lần đều ra cùng một vị trí) là (1/4)^39 — coi như không xảy ra.
        assertThat(positions.stream().distinct().count())
                .as("40 lần sinh mà đáp án luôn ở cùng một vị trí nghĩa là không hề xáo")
                .isGreaterThan(1L);
    }
}
