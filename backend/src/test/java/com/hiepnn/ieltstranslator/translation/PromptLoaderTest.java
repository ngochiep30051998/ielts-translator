package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class PromptLoaderTest {

    private final PromptLoader loader = new PromptLoader();

    @ParameterizedTest
    @CsvSource({
        "EN_VI, WORD", "EN_VI, SENTENCE", "VI_EN, WORD", "VI_EN, SENTENCE"
    })
    void loadsAllFourTemplates(Direction direction, Mode mode) {
        PromptTemplate template = loader.load(direction, mode);

        assertThat(template.version()).isGreaterThanOrEqualTo(1);
        assertThat(template.body()).isNotBlank();
        assertThat(template.body()).doesNotStartWith("version:");
    }

    @Test
    void headerIsStrippedButBodyKeepsFieldNamesContainingVersion() {
        PromptTemplate template = loader.load(Direction.VI_EN, Mode.SENTENCE);

        assertThat(template.version()).isEqualTo(1);
        assertThat(template.body()).doesNotStartWith("version:");
        // band65_version là tên trường trong schema, KHÔNG phải header sót lại
        assertThat(template.body()).contains("band65_version");
    }

    @Test
    void renderSubstitutesTextAndContext() {
        PromptTemplate template = new PromptTemplate(
                "Tra từ: {{TEXT}}\nNgữ cảnh: {{CONTEXT}}", 1);

        String rendered = template.render("renewable", "We need renewable energy.");

        assertThat(rendered).isEqualTo("Tra từ: renewable\nNgữ cảnh: We need renewable energy.");
    }

    @Test
    void renderHandlesNullContext() {
        PromptTemplate template = new PromptTemplate("{{TEXT}}|{{CONTEXT}}", 1);

        assertThat(template.render("x", null)).isEqualTo("x|(không có ngữ cảnh)");
    }

    @Test
    void everyTemplateContainsTextPlaceholder() {
        for (Direction d : Direction.values()) {
            for (Mode m : Mode.values()) {
                assertThat(loader.load(d, m).body())
                        .as("%s/%s phải có {{TEXT}}", d, m)
                        .contains("{{TEXT}}");
            }
        }
    }
}
