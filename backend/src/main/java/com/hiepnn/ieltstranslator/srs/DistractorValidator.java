package com.hiepnn.ieltstranslator.srs;

import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Kiểm tra bộ mồi nhử Gemini trả về. Hàm thuần — không DB, không mạng.
 *
 * <p>Loại CẢ bộ khi có bất kỳ vi phạm nào, thay vì cố vá từng phần tử: bộ đã hỏng thì
 * phần còn lại cũng không đáng tin, và để lần sau sinh lại rẻ hơn nhiều so với việc
 * người học gặp một câu hỏi có hai đáp án cùng đúng.
 */
@Component
public class DistractorValidator {

    private static final int REQUIRED_COUNT = 3;

    public boolean isValid(DistractorSet set, String meaningVi, String term) {
        if (set == null) {
            return false;
        }
        return sideIsValid(set.viOptions(), meaningVi)
                && sideIsValid(set.enOptions(), term);
    }

    /** Một chiều hợp lệ khi đủ 3 phần tử, không rỗng, không trùng nhau, không trùng đáp án đúng. */
    private boolean sideIsValid(List<String> options, String correctAnswer) {
        if (options == null || options.size() != REQUIRED_COUNT) {
            return false;
        }
        Set<String> seen = new HashSet<>();
        String correct = normalise(correctAnswer);
        for (String option : options) {
            if (option == null || option.isBlank()) {
                return false;
            }
            String key = normalise(option);
            if (key.equals(correct) || !seen.add(key)) {
                return false;
            }
        }
        return true;
    }

    private String normalise(String value) {
        return value == null ? "" : value.strip().toLowerCase(Locale.ROOT);
    }
}
