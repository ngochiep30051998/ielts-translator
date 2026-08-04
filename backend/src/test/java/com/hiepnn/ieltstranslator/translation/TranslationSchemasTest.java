package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class TranslationSchemasTest {

    @SuppressWarnings("unchecked")
    private List<String> requiredOf(Direction d, Mode m) {
        return (List<String>) TranslationSchemas.of(d, m).get("required");
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> nested(Direction d, Mode m, String arrayProperty) {
        Map<String, Object> schema = TranslationSchemas.of(d, m);
        Map<String, Object> properties = (Map<String, Object>) schema.get("properties");
        Map<String, Object> array = (Map<String, Object>) properties.get(arrayProperty);
        return (Map<String, Object>) array.get("items");
    }

    @SuppressWarnings("unchecked")
    private Set<String> keysOf(Map<String, Object> objectSchema) {
        return ((Map<String, Object>) objectSchema.get("properties")).keySet();
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
    void enViWordNestedFieldNamesArePinned() {
        assertThat(keysOf(nested(Direction.EN_VI, Mode.WORD, "examples")))
                .containsExactlyInAnyOrder("en", "vi");
        assertThat(keysOf(nested(Direction.EN_VI, Mode.WORD, "synonyms")))
                .containsExactlyInAnyOrder("term", "band");
    }

    @Test
    void enViSentenceNestedFieldNamesArePinned() {
        assertThat(keysOf(nested(Direction.EN_VI, Mode.SENTENCE, "key_vocab")))
                .containsExactlyInAnyOrder("term", "meaning_vi", "band_level");
    }

    @Test
    void viEnWordNestedFieldNamesArePinned() {
        assertThat(keysOf(nested(Direction.VI_EN, Mode.WORD, "alternatives")))
                .containsExactlyInAnyOrder("term", "band", "register", "when_to_use");
    }

    @Test
    void viEnSentenceNestedFieldNamesArePinned() {
        assertThat(keysOf(nested(Direction.VI_EN, Mode.SENTENCE, "avoid")))
                .containsExactlyInAnyOrder("phrase", "reason");
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
