package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class TranslationSchemasTest {

    @SuppressWarnings("unchecked")
    private List<String> requiredOf(Direction d, Mode m) {
        return (List<String>) TranslationSchemas.of(d, m).get("required");
    }

    @Test
    void enViWordRequiresBubbleAndDetailFields() {
        assertThat(requiredOf(Direction.EN_VI, Mode.WORD))
                .contains("term", "ipa", "pos", "meaning_vi", "definition_en",
                          "cefr", "band_level", "register", "collocations",
                          "examples", "synonyms");
    }

    @Test
    void enViSentenceRequiresTranslationAndKeyVocab() {
        assertThat(requiredOf(Direction.EN_VI, Mode.SENTENCE))
                .contains("translation_vi", "key_vocab", "structure_note");
    }

    @Test
    void viEnWordRequiresBestEnAndAlternatives() {
        assertThat(requiredOf(Direction.VI_EN, Mode.WORD))
                .contains("best_en", "alternatives", "collocations", "examples");
    }

    @Test
    void viEnSentenceRequiresBandVersionAndExplanations() {
        assertThat(requiredOf(Direction.VI_EN, Mode.SENTENCE))
                .contains("band65_version", "why_notes", "key_phrases", "avoid");
    }

    @Test
    void allSchemasAreObjectsWithProperties() {
        for (Direction d : Direction.values()) {
            for (Mode m : Mode.values()) {
                Map<String, Object> schema = TranslationSchemas.of(d, m);
                assertThat(schema.get("type")).as("%s/%s", d, m).isEqualTo("object");
                assertThat(schema.get("properties")).as("%s/%s", d, m).isInstanceOf(Map.class);
            }
        }
    }
}
