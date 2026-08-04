package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class ModeTest {

    @ParameterizedTest(name = "[{index}] \"{0}\" -> {1}")
    @CsvSource(delimiter = '|', value = {
        "renewable                             | WORD",
        "climate change                        | WORD",
        "renewable energy sources              | WORD",
        "  renewable   energy   sources        | WORD",
        "the government should allocate funding | SENTENCE",
        "năng lượng tái tạo là xu hướng        | SENTENCE"
    })
    void classifiesMode(String text, Mode expected) {
        assertThat(Mode.of(text)).isEqualTo(expected);
    }
}
