package com.hiepnn.ieltstranslator.quiz;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class QuizMigrationIT extends AbstractPostgresIT {

    @Autowired VocabEntryRepository vocab;
    @Autowired QuizItemRepository items;
    @Autowired QuizAttemptRepository attempts;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM quiz_attempt");
        jdbc.update("DELETE FROM quiz_item");
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM srs_distractor");
        jdbc.update("DELETE FROM vocab_entry");
    }

    private VocabEntry savedEntry() {
        VocabEntry v = new VocabEntry();
        v.setTerm("mitigate");
        v.setLemma("mitigate");
        v.setLang("en");
        v.setPos("verb");
        v.setMeaningVi("giảm nhẹ");
        v.setCollocations(objectMapper.createArrayNode());
        v.setExamples(objectMapper.createArrayNode());
        return vocab.saveAndFlush(v);
    }

    private QuizItem savedItem(VocabEntry v) {
        QuizItem item = new QuizItem();
        item.setVocabEntry(v);
        item.setType(QuizType.FILL_BLANK);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("sentence", "We must ___ the risk.");
        payload.put("answer", "mitigate");
        item.setPayload(payload);
        item.setPromptVersion(1);
        return items.saveAndFlush(item);
    }

    @Test
    @DisplayName("V5 dựng được bảng và entity khớp schema — payload JSONB đọc lại nguyên vẹn")
    void persistsItemAndAttempt() {
        QuizItem item = savedItem(savedEntry());

        QuizAttempt attempt = new QuizAttempt();
        attempt.setQuizItem(item);
        attempt.setUserAnswer("mitigate");
        attempt.setCorrect(true);
        attempt.setScore(100);
        attempt.setAiFeedback(null);
        attempt.setImprovedVersion(null);
        attempts.saveAndFlush(attempt);

        QuizItem reloaded = items.findById(item.getId()).orElseThrow();
        assertThat(reloaded.getPayload()).containsEntry("answer", "mitigate");
        assertThat(reloaded.getType()).isEqualTo(QuizType.FILL_BLANK);
        assertThat(attempts.count()).isEqualTo(1L);
    }

    @Test
    @DisplayName("Cột improved_version lưu và đọc lại được — chỗ duy nhất giữ câu Gemini viết lại")
    void persistsImprovedVersion() {
        QuizItem item = savedItem(savedEntry());

        QuizAttempt attempt = new QuizAttempt();
        attempt.setQuizItem(item);
        attempt.setUserAnswer("We must mitigate it.");
        attempt.setCorrect(true);
        attempt.setScore(90);
        attempt.setAiFeedback("Câu ổn.");
        attempt.setImprovedVersion("We must mitigate the risk effectively.");
        attempts.saveAndFlush(attempt);

        assertThat(jdbc.queryForObject(
                "SELECT improved_version FROM quiz_attempt WHERE id = ?", String.class,
                attempt.getId()))
                .isEqualTo("We must mitigate the risk effectively.");
    }

    @Test
    @DisplayName("Xoá từ trong sổ cascade sạch quiz_item và quiz_attempt")
    void cascadesFromVocabEntry() {
        VocabEntry v = savedEntry();
        QuizItem item = savedItem(v);
        QuizAttempt attempt = new QuizAttempt();
        attempt.setQuizItem(item);
        attempt.setUserAnswer("x");
        attempt.setCorrect(false);
        attempt.setScore(0);
        attempts.saveAndFlush(attempt);

        jdbc.update("DELETE FROM vocab_entry WHERE id = ?", v.getId());

        assertThat(items.count()).isZero();
        assertThat(attempts.count()).isZero();
    }

    @Test
    @DisplayName("findReusable bỏ qua item đã có lượt làm và item sai prompt_version")
    void reusableSkipsAttemptedAndStaleItems() {
        VocabEntry v = savedEntry();
        QuizItem fresh = savedItem(v);

        QuizItem attempted = savedItem(v);
        QuizAttempt attempt = new QuizAttempt();
        attempt.setQuizItem(attempted);
        attempt.setUserAnswer("x");
        attempt.setCorrect(false);
        attempt.setScore(0);
        attempts.saveAndFlush(attempt);

        QuizItem stale = savedItem(v);
        stale.setPromptVersion(99);
        items.saveAndFlush(stale);

        assertThat(items.findReusable(List.of(v.getId()), List.of(QuizType.FILL_BLANK), 1))
                .extracting(QuizItem::getId)
                .containsExactly(fresh.getId());
    }
}
