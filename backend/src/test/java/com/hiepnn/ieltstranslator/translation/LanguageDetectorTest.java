package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class LanguageDetectorTest {

    private final LanguageDetector detector = new LanguageDetector();

    @ParameterizedTest(name = "[{index}] \"{0}\" -> {1}")
    @CsvSource(delimiter = '|', value = {
        // tiếng Việt có dấu -> nhận ra ngay bằng ký tự
        "Chính phủ nên đầu tư nhiều hơn vào năng lượng tái tạo | VI_EN",
        "tái tạo                                               | VI_EN",
        "Tôi thích renewable energy                            | VI_EN",
        // tiếng Việt không dấu -> nhận ra bằng stopword
        "toi khong biet cai nay la cua ai                      | VI_EN",
        "chung ta can phai lam viec nay cho tot               | VI_EN",
        // tiếng Anh
        "renewable                                             | EN_VI",
        "The government should allocate more funding           | EN_VI",
        "this is a test of the system                          | EN_VI",
        // không quyết được -> mặc định EN_VI
        "12345                                                 | EN_VI",
        "'  '                                                  | EN_VI"
    })
    void detectsDirection(String text, Direction expected) {
        assertThat(detector.detect(text)).isEqualTo(expected);
    }

    @Test
    void emptyTextDefaultsToEnVi() {
        assertThat(detector.detect("")).isEqualTo(Direction.EN_VI);
    }

    @Test
    void nullTextDefaultsToEnVi() {
        assertThat(detector.detect(null)).isEqualTo(Direction.EN_VI);
    }
}
