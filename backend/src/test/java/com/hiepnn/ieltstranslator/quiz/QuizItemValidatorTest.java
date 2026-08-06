package com.hiepnn.ieltstranslator.quiz;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class QuizItemValidatorTest {

    private final QuizItemValidator validator = new QuizItemValidator();

    /* ---------- FILL_BLANK ---------- */

    @Test
    @DisplayName("Câu có ___ và đáp án không lộ ở đâu cả thì hợp lệ")
    void acceptsValidFillBlank() {
        assertThat(validator.isValidFillBlank(
                "Governments must ___ the effects of climate change.", "mitigate",
                "động từ, làm cho nhẹ bớt")).isTrue();
    }

    @Test
    @DisplayName("Câu thiếu ___ thì loại — không có chỗ trống thì không phải câu điền từ")
    void rejectsSentenceWithoutBlank() {
        assertThat(validator.isValidFillBlank(
                "Governments must mitigate the effects.", "mitigate", "gợi ý")).isFalse();
    }

    @Test
    @DisplayName("Đáp án lộ nguyên văn ở chỗ khác trong câu thì loại")
    void rejectsAnswerLeakedInSentence() {
        assertThat(validator.isValidFillBlank(
                "To mitigate risk, we must ___ the impact.", "mitigate", "gợi ý")).isFalse();
    }

    @Test
    @DisplayName("Đáp án lộ khác hoa thường vẫn là lộ — người học vẫn đọc thấy")
    void rejectsAnswerLeakedIgnoringCase() {
        assertThat(validator.isValidFillBlank(
                "Mitigate is the key: we must ___ the impact.", "mitigate", "gợi ý")).isFalse();
    }

    @Test
    @DisplayName("Đáp án rỗng hoặc chỉ khoảng trắng thì loại")
    void rejectsBlankAnswer() {
        assertThat(validator.isValidFillBlank("We must ___ it.", "   ", "gợi ý")).isFalse();
        assertThat(validator.isValidFillBlank("We must ___ it.", "", "gợi ý")).isFalse();
    }

    @Test
    @DisplayName("Hint rỗng thì loại — question của FILL_BLANK dựng từ hint, rỗng là đề cụt")
    void rejectsBlankHint() {
        assertThat(validator.isValidFillBlank("We must ___ it.", "mitigate", "")).isFalse();
        assertThat(validator.isValidFillBlank("We must ___ it.", "mitigate", "   ")).isFalse();
        assertThat(validator.isValidFillBlank("We must ___ it.", "mitigate", null)).isFalse();
    }

    @Test
    @DisplayName("Hint chứa đáp án thì loại — gợi ý mà lộ đáp án thì câu hỏi vô nghĩa")
    void rejectsHintContainingAnswer() {
        assertThat(validator.isValidFillBlank(
                "We must ___ it.", "mitigate", "dùng từ mitigate")).isFalse();
        assertThat(validator.isValidFillBlank(
                "We must ___ it.", "mitigate", "dùng từ MITIGATE")).isFalse();
    }

    @Test
    @DisplayName("null ở đâu cũng loại, không ném NPE")
    void rejectsNullsFillBlank() {
        assertThat(validator.isValidFillBlank(null, "mitigate", "gợi ý")).isFalse();
        assertThat(validator.isValidFillBlank("We must ___ it.", null, "gợi ý")).isFalse();
    }

    /* ---------- COLLOCATION_CHOICE ---------- */

    @Test
    @DisplayName("Đúng 4 lựa chọn khác nhau và index trong khoảng thì hợp lệ")
    void acceptsValidCollocation() {
        assertThat(validator.isValidCollocation(
                List.of("mitigate risk", "mitigate a cake", "mitigate loudly", "mitigate blue"), 0))
                .isTrue();
    }

    @Test
    @DisplayName("Ba hoặc năm lựa chọn thì loại — UI dựng đúng 4 ô")
    void rejectsWrongOptionCount() {
        assertThat(validator.isValidCollocation(List.of("a", "b", "c"), 0)).isFalse();
        assertThat(validator.isValidCollocation(List.of("a", "b", "c", "d", "e"), 0)).isFalse();
    }

    @Test
    @DisplayName("Hai lựa chọn trùng nhau thì loại — hai ô cùng nội dung là câu hỏi hỏng")
    void rejectsDuplicateOptions() {
        assertThat(validator.isValidCollocation(
                List.of("mitigate risk", "Mitigate Risk", "c", "d"), 0)).isFalse();
    }

    @Test
    @DisplayName("Lựa chọn rỗng thì loại")
    void rejectsBlankOption() {
        assertThat(validator.isValidCollocation(List.of("a", "  ", "c", "d"), 0)).isFalse();
    }

    @Test
    @DisplayName("correct_index ngoài khoảng 0..3 thì loại")
    void rejectsIndexOutOfRange() {
        assertThat(validator.isValidCollocation(List.of("a", "b", "c", "d"), -1)).isFalse();
        assertThat(validator.isValidCollocation(List.of("a", "b", "c", "d"), 4)).isFalse();
    }

    @Test
    @DisplayName("null ở đâu cũng loại, không ném NPE")
    void rejectsNullsCollocation() {
        assertThat(validator.isValidCollocation(null, 0)).isFalse();
        assertThat(validator.isValidCollocation(List.of("a", "b", "c", "d"), null)).isFalse();
        assertThat(validator.isValidCollocation(Arrays.asList("a", null, "c", "d"), 0)).isFalse();
    }
}
