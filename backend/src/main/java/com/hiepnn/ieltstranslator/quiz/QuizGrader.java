package com.hiepnn.ieltstranslator.quiz;

import org.springframework.stereotype.Component;

/**
 * Chấm hai loại quiz chấm được tại chỗ. Hàm thuần — không DB, không mạng, không Gemini.
 */
@Component
public class QuizGrader {

    /**
     * So với đúng dạng từ đã bị che. CỐ Ý không lemmatize: đề che dạng "mitigated" thì
     * người học phải viết "mitigated". Chấp nhận "mitigate" là dạy sai — chia động từ
     * đúng chính là thứ đang luyện.
     *
     * <p>Dùng {@code equalsIgnoreCase} chứ không phải regex: nó đã xử lý đúng Unicode,
     * không dính bẫy {@code Pattern.CASE_INSENSITIVE} thiếu {@code UNICODE_CASE}.
     */
    public boolean gradeFillBlank(String userAnswer, String expected) {
        if (userAnswer == null || expected == null) {
            return false;
        }
        String given = userAnswer.trim();
        return !given.isEmpty() && given.equalsIgnoreCase(expected.trim());
    }

    /**
     * Answer đi trên đường truyền LUÔN là string (một hình dạng, không union). Chuỗi
     * không parse được thành index tính là SAI, không phải lỗi — người dùng gõ bậy
     * không phải sự cố hệ thống, và ném ở đây sẽ biến nó thành HTTP 500.
     */
    public boolean gradeCollocation(String userAnswer, int correctIndex) {
        if (userAnswer == null) {
            return false;
        }
        try {
            return Integer.parseInt(userAnswer.trim()) == correctIndex;
        } catch (NumberFormatException ex) {
            return false;
        }
    }
}
