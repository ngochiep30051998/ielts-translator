package com.hiepnn.ieltstranslator.quiz;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
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
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.when;

/**
 * Bất biến quan trọng nhất của Phase 3: làm quiz KHÔNG được đụng vào lịch ôn SRS.
 *
 * <p>Chụp ảnh trước/sau bằng JdbcTemplate chứ không qua JPA — cache phiên của JPA có thể
 * trả lại đúng object cũ và làm phép so xanh giả.
 */
class QuizSrsIsolationIT extends AbstractPostgresIT {

    @Autowired QuizService service;
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

    private Long seed(String term, int repetitions, int lapses) {
        VocabEntry v = new VocabEntry();
        v.setTerm(term);
        v.setLemma(term);
        v.setLang("en");
        v.setPos("verb");
        v.setMeaningVi("nghĩa của " + term);
        v.setCollocations(objectMapper.createArrayNode());
        v.setExamples(objectMapper.createArrayNode());
        Long id = vocab.saveAndFlush(v).getId();
        jdbc.update("""
                INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses,
                                      ease_factor, interval_days)
                VALUES (?, CURRENT_DATE + 3, 'REVIEW', ?, ?, 2.36, 7)""",
                id, repetitions, lapses);
        return id;
    }

    private List<Map<String, Object>> srsSnapshot() {
        return jdbc.queryForList("""
                SELECT id, vocab_entry_id, ease_factor, interval_days, repetitions, lapses,
                       due_date, state
                FROM srs_card ORDER BY id""");
    }

    private List<Map<String, Object>> reviewLogSnapshot() {
        return jdbc.queryForList("""
                SELECT id, card_id, rating, prev_interval, new_interval
                FROM review_log ORDER BY id""");
    }

    /**
     * Gieo sẵn lịch sử ôn để phép so cuối bài có gì để so.
     *
     * <p>Không có bước này thì {@code review_log} rỗng suốt bài và khẳng định "không đổi
     * dòng nào" rút về {@code 0 == 0} — nó bắt được ca INSERT nhưng bỏ lọt hoàn toàn ca
     * một hồi quy tương lai SỬA hoặc XOÁ dòng có sẵn (ví dụ ai đó thêm "làm quiz đúng thì
     * hạ lapses của lượt ôn gần nhất").
     */
    private void seedReviewLog(Long vocabEntryId) {
        Long cardId = jdbc.queryForObject(
                "SELECT id FROM srs_card WHERE vocab_entry_id = ?", Long.class, vocabEntryId);
        jdbc.update("""
                INSERT INTO review_log (card_id, rating, prev_interval, new_interval)
                VALUES (?, 'GOOD', 0, 1), (?, 'HARD', 1, 2)""", cardId, cardId);
    }

    @Test
    @DisplayName("Làm hết một đề cả ba loại xong, srs_card và review_log không đổi một dòng nào")
    void quizNeverTouchesSrs() throws Exception {
        Long firstVocabId = seed("mitigate", 3, 1);
        seed("resilient", 5, 0);
        seedReviewLog(firstVocabId);

        List<Map<String, Object>> before = srsSnapshot();
        List<Map<String, Object>> reviewLogBefore = reviewLogSnapshot();
        assertThat(before).hasSize(2);
        // Chốt chống phép so rỗng: có dòng thật thì so snapshot mới có nghĩa.
        assertThat(reviewLogBefore).hasSize(2);

        int answered = 0;
        answered += doWholeQuiz(QuizType.FILL_BLANK);
        answered += doWholeQuiz(QuizType.COLLOCATION_CHOICE);
        answered += doWholeQuiz(QuizType.FREE_WRITE);

        // Không có điểm này thì test xanh cả khi code chết: "không đổi gì" là hiển nhiên
        // khi chẳng có gì chạy.
        assertThat(answered).isPositive();
        assertThat(attempts.count()).isEqualTo(answered);

        assertThat(srsSnapshot()).isEqualTo(before);
        // So snapshot từng cột, không so count(*): count bắt được INSERT/DELETE nhưng
        // không bắt được UPDATE một dòng có sẵn.
        assertThat(reviewLogSnapshot()).isEqualTo(reviewLogBefore);
    }

    /** Sinh đề một loại rồi nộp hết, cả câu đúng lẫn câu sai. @return số câu đã nộp. */
    private int doWholeQuiz(QuizType type) throws Exception {
        stubFor(type);
        List<QuizItemDto> generated = service.generate(new GenerateQuizRequest(null, 10, type));
        assertThat(generated).as("%s phải sinh được đề", type).isNotEmpty();

        if (type == QuizType.FREE_WRITE) {
            when(geminiClient.generateJson(anyString(), any(), any()))
                    .thenReturn(objectMapper.readTree("""
                    {"meaning_ok":true,"grammar_ok":false,"band_ok":false,"score":55,
                     "feedback_vi":"Ngữ pháp còn lỗi.","improved_version":"Better."}"""));
        }

        int index = 0;
        for (QuizItemDto item : generated) {
            // Xen kẽ đúng/sai để chắc chắn cả hai nhánh chấm đều chạy.
            service.answer(item.id(), index % 2 == 0 ? "0" : "câu trả lời bất kỳ");
            index++;
        }
        return generated.size();
    }

    private void stubFor(QuizType type) throws Exception {
        if (type == QuizType.FILL_BLANK) {
            when(geminiClient.generateJson(anyString(), any(), any()))
                    .thenReturn(objectMapper.readTree("""
                    {"items":[
                      {"term":"mitigate","sentence":"They must ___ it.","answer":"mitigate","hint":"gợi ý"},
                      {"term":"resilient","sentence":"She is ___ enough.","answer":"resilient","hint":"gợi ý"}
                    ]}"""));
        } else if (type == QuizType.COLLOCATION_CHOICE) {
            when(geminiClient.generateJson(anyString(), any(), any()))
                    .thenReturn(objectMapper.readTree("""
                    {"items":[
                      {"term":"mitigate","question":"Cụm nào tự nhiên?",
                       "options":["mitigate risk","mitigate cake","mitigate blue","mitigate loud"],
                       "correct_index":0},
                      {"term":"resilient","question":"Cụm nào tự nhiên?",
                       "options":["resilient economy","resilient cake","resilient blue","resilient loud"],
                       "correct_index":0}
                    ]}"""));
        }
    }
}
