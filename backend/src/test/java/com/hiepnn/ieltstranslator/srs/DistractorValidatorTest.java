package com.hiepnn.ieltstranslator.srs;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DistractorValidatorTest {

    private final DistractorValidator validator = new DistractorValidator();

    private static final String MEANING = "giảm nhẹ";
    private static final String TERM = "mitigate";

    private static DistractorSet set(List<String> vi, List<String> en) {
        return new DistractorSet(vi, en);
    }

    private static DistractorSet valid() {
        return set(List.of("làm trầm trọng thêm", "phóng đại", "trì hoãn"),
                   List.of("aggravate", "exaggerate", "postpone"));
    }

    @Test
    @DisplayName("Bộ mồi nhử đủ 3 phần tử mỗi chiều, không trùng, không đụng đáp án đúng thì hợp lệ")
    void acceptsValidSet() {
        assertThat(validator.isValid(valid(), MEANING, TERM)).isTrue();
    }

    @Test
    @DisplayName("Thiếu phần tử thì loại")
    void rejectsTooFew() {
        assertThat(validator.isValid(
                set(List.of("làm trầm trọng thêm", "phóng đại"),
                    List.of("aggravate", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Thừa phần tử thì loại — Gemini trả 4 nghĩa là dấu hiệu nó hiểu sai đề")
    void rejectsTooMany() {
        assertThat(validator.isValid(
                set(List.of("a", "b", "c"),
                    List.of("aggravate", "exaggerate", "postpone", "delay")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Phần tử rỗng hoặc chỉ có khoảng trắng thì loại")
    void rejectsBlank() {
        assertThat(validator.isValid(
                set(List.of("làm trầm trọng thêm", "   ", "trì hoãn"),
                    List.of("aggravate", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Hai phần tử trùng nhau trong cùng một chiều thì loại")
    void rejectsDuplicatesWithinSide() {
        assertThat(validator.isValid(
                set(List.of("phóng đại", "Phóng Đại", "trì hoãn"),
                    List.of("aggravate", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Mồi nhử trùng nghĩa đúng thì loại — hai lựa chọn cùng đúng là giết bài ôn")
    void rejectsWhenViOptionEqualsMeaning() {
        assertThat(validator.isValid(
                set(List.of("  Giảm Nhẹ ", "phóng đại", "trì hoãn"),
                    List.of("aggravate", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Mồi nhử trùng chính từ đang hỏi thì loại")
    void rejectsWhenEnOptionEqualsTerm() {
        assertThat(validator.isValid(
                set(List.of("làm trầm trọng thêm", "phóng đại", "trì hoãn"),
                    List.of("MITIGATE", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("null ở bất kỳ đâu thì loại, không ném NPE")
    void rejectsNulls() {
        assertThat(validator.isValid(null, MEANING, TERM)).isFalse();
        assertThat(validator.isValid(set(null, List.of("a", "b", "c")), MEANING, TERM)).isFalse();
        assertThat(validator.isValid(
                set(Arrays.asList("a", null, "c"), List.of("x", "y", "z")),
                MEANING, TERM)).isFalse();
    }
}
