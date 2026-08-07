package com.hiepnn.ieltstranslator.quiz;

import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Kiểm tra từng item Gemini trả về. Hàm thuần — không DB, không mạng.
 *
 * <p>Khác {@code DistractorValidator} một cách CÓ CHỦ Ý: ở đây loại TỪNG item hỏng rồi
 * lấy tiếp phần còn lại, không giết cả lô. Một lô 10 câu mà hỏng 1 câu thì 9 câu kia vẫn
 * dùng được, và người dùng đang đứng chờ — bắt họ đợi thêm một lượt gọi Gemini nữa chỉ
 * vì một câu hỏng là đắt vô lý. Bên mồi nhử thì ngược lại: việc chạy nền, không ai chờ.
 */
@Component
public class QuizItemValidator {

    /** Chỗ trống trong câu điền từ. Đúng ba gạch dưới, khớp với prompt. */
    public static final String BLANK = "___";

    private static final int REQUIRED_OPTIONS = 4;

    /**
     * Hợp lệ khi: câu chứa {@code ___}, đáp án không rỗng, đáp án KHÔNG xuất hiện nguyên
     * văn ở phần còn lại của câu, và gợi ý khác rỗng mà cũng không chứa đáp án (bỏ phân
     * biệt hoa thường ở cả hai phép so).
     *
     * <p>Vì sao hint cũng bị soi: {@code question} của FILL_BLANK được dựng thành
     * "Điền từ còn thiếu vào chỗ trống. Gợi ý: " + hint, nên hint rỗng cho ra một đề cụt,
     * còn hint chứa đáp án thì lộ đáp án ngay trên đề — đúng thứ mà DTO đang cố giấu.
     */
    public boolean isValidFillBlank(String sentence, String answer, String hint) {
        if (sentence == null || answer == null || answer.isBlank()) {
            return false;
        }
        if (hint == null || hint.isBlank()) {
            return false;
        }
        if (!sentence.contains(BLANK)) {
            return false;
        }
        String needle = answer.trim().toLowerCase(Locale.ROOT);
        String withoutBlank = sentence.replace(BLANK, " ").toLowerCase(Locale.ROOT);
        if (withoutBlank.contains(needle)) {
            return false;
        }
        return !hint.toLowerCase(Locale.ROOT).contains(needle);
    }

    /** Hợp lệ khi: đúng 4 lựa chọn, không rỗng, không trùng nhau, index trong 0..3. */
    public boolean isValidCollocation(List<String> options, Integer correctIndex) {
        if (options == null || correctIndex == null || options.size() != REQUIRED_OPTIONS) {
            return false;
        }
        if (correctIndex < 0 || correctIndex >= REQUIRED_OPTIONS) {
            return false;
        }
        Set<String> seen = new HashSet<>();
        for (String option : options) {
            if (option == null || option.isBlank()) {
                return false;
            }
            if (!seen.add(option.trim().toLowerCase(Locale.ROOT))) {
                return false;
            }
        }
        return true;
    }
}
