package com.hiepnn.ieltstranslator.quiz;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class QuizGraderTest {

    private final QuizGrader grader = new QuizGrader();

    @Test
    @DisplayName("Khớp chính xác thì đúng")
    void exactMatchIsCorrect() {
        assertThat(grader.gradeFillBlank("mitigate", "mitigate")).isTrue();
    }

    @Test
    @DisplayName("Thừa khoảng trắng hai đầu vẫn đúng")
    void trimsWhitespace() {
        assertThat(grader.gradeFillBlank("  mitigate  ", "mitigate")).isTrue();
    }

    @Test
    @DisplayName("Khác hoa thường vẫn đúng")
    void ignoresCase() {
        assertThat(grader.gradeFillBlank("MITIGATE", "mitigate")).isTrue();
        assertThat(grader.gradeFillBlank("Mitigate", "mitigate")).isTrue();
    }

    @Test
    @DisplayName("KHÔNG lemmatize — sai dạng từ là sai")
    void doesNotLemmatize() {
        assertThat(grader.gradeFillBlank("mitigate", "mitigated")).isFalse();
        assertThat(grader.gradeFillBlank("mitigating", "mitigate")).isFalse();
        assertThat(grader.gradeFillBlank("mitigates", "mitigate")).isFalse();
    }

    @Test
    @DisplayName("Rỗng, chỉ khoảng trắng, hoặc null đều là sai, không ném NPE")
    void blankIsWrong() {
        assertThat(grader.gradeFillBlank("", "mitigate")).isFalse();
        assertThat(grader.gradeFillBlank("   ", "mitigate")).isFalse();
        assertThat(grader.gradeFillBlank(null, "mitigate")).isFalse();
        assertThat(grader.gradeFillBlank("mitigate", null)).isFalse();
    }

    @Test
    @DisplayName("Chọn đúng index thì đúng")
    void collocationIndexMatch() {
        assertThat(grader.gradeCollocation("2", 2)).isTrue();
        assertThat(grader.gradeCollocation(" 2 ", 2)).isTrue();
    }

    @Test
    @DisplayName("Chọn sai index thì sai")
    void collocationIndexMismatch() {
        assertThat(grader.gradeCollocation("1", 2)).isFalse();
    }

    @Test
    @DisplayName("Answer không parse được thành số tính là SAI, không phải lỗi")
    void garbageAnswerIsWrongNotError() {
        assertThat(grader.gradeCollocation("hai", 2)).isFalse();
        assertThat(grader.gradeCollocation("", 2)).isFalse();
        assertThat(grader.gradeCollocation(null, 2)).isFalse();
        assertThat(grader.gradeCollocation("2.0", 2)).isFalse();
        assertThat(grader.gradeCollocation("99999999999999999999", 2)).isFalse();
    }
}
