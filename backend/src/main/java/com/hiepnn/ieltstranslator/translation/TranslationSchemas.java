package com.hiepnn.ieltstranslator.translation;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Response schema gửi cho Gemini (tập con OpenAPI mà Gemini chấp nhận). */
public final class TranslationSchemas {

    private static final List<String> BANDS =
            List.of("5.5", "6.0", "6.5", "7.0", "7.5", "8.0");

    private TranslationSchemas() {}

    public static Map<String, Object> of(Direction direction, Mode mode) {
        if (direction == Direction.EN_VI) {
            return mode == Mode.WORD ? enViWord() : enViSentence();
        }
        return mode == Mode.WORD ? viEnWord() : viEnSentence();
    }

    private static Map<String, Object> enViWord() {
        return object(
                Map.of("term", str(), "lemma", str(), "pos", str(), "ipa", str(),
                       "meaning_vi", str(), "definition_en", str(),
                       "cefr", enumOf(List.of("A1", "A2", "B1", "B2", "C1", "C2")),
                       "band_level", enumOf(BANDS),
                       "register", enumOf(List.of("academic", "neutral", "informal")),
                       "collocations", arrayOf(str())),
                Map.of("examples", arrayOf(object(
                               Map.of("en", str(), "vi", str()), List.of("en", "vi"))),
                       "synonyms", arrayOf(object(
                               Map.of("term", str(), "band", enumOf(BANDS)), List.of("term", "band")))),
                List.of("term", "lemma", "pos", "ipa", "meaning_vi", "definition_en",
                        "cefr", "band_level", "register", "collocations", "examples", "synonyms"));
    }

    private static Map<String, Object> enViSentence() {
        return object(
                Map.of("translation_vi", str(),
                       "key_vocab", arrayOf(object(
                               Map.of("term", str(), "meaning_vi", str(), "band_level", enumOf(BANDS)),
                               List.of("term", "meaning_vi", "band_level"))),
                       "structure_note", str()),
                Map.of(),
                List.of("translation_vi", "key_vocab", "structure_note"));
    }

    private static Map<String, Object> viEnWord() {
        return object(
                Map.of("best_en", str(),
                       "alternatives", arrayOf(object(
                               Map.of("term", str(), "band", enumOf(BANDS),
                                      "register", enumOf(List.of("academic", "neutral", "informal")),
                                      "when_to_use", str()),
                               List.of("term", "band", "register", "when_to_use"))),
                       "collocations", arrayOf(str()),
                       "examples", arrayOf(str())),
                Map.of(),
                List.of("best_en", "alternatives", "collocations", "examples"));
    }

    private static Map<String, Object> viEnSentence() {
        return object(
                Map.of("band65_version", str(),
                       "why_notes", arrayOf(str()),
                       "key_phrases", arrayOf(str()),
                       "avoid", arrayOf(object(
                               Map.of("phrase", str(), "reason", str()),
                               List.of("phrase", "reason")))),
                Map.of(),
                List.of("band65_version", "why_notes", "key_phrases", "avoid"));
    }

    // --- helper dựng schema ---

    private static Map<String, Object> str() {
        return Map.of("type", "string");
    }

    private static Map<String, Object> enumOf(List<String> values) {
        return Map.of("type", "string", "enum", values);
    }

    private static Map<String, Object> arrayOf(Map<String, Object> items) {
        return Map.of("type", "array", "items", items);
    }

    private static Map<String, Object> object(Map<String, Object> props, List<String> required) {
        return object(props, Map.of(), required);
    }

    /** Gộp hai map property để né giới hạn 10 cặp của Map.of(). */
    private static Map<String, Object> object(Map<String, Object> propsA,
                                              Map<String, Object> propsB,
                                              List<String> required) {
        Map<String, Object> properties = new LinkedHashMap<>();
        properties.putAll(propsA);
        properties.putAll(propsB);
        Map<String, Object> schema = new LinkedHashMap<>();
        schema.put("type", "object");
        schema.put("properties", properties);
        schema.put("required", required);
        return schema;
    }
}
