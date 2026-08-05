package com.hiepnn.ieltstranslator.vocabulary;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class CsvExporterTest {

    private final CsvExporter exporter = new CsvExporter();

    private VocabEntry entry(String term, String meaning, List<String> tags) {
        VocabEntry e = new VocabEntry();
        e.setTerm(term);
        e.setPos("adj");
        e.setIpa("/test/");
        e.setMeaningVi(meaning);
        e.setDefinitionEn("a definition");
        e.setCefr("B2");
        e.setBandLevel("6.5");
        e.setTags(tags.toArray(new String[0]));
        e.setSourceUrl("https://example.com");
        e.setCreatedAt(Instant.parse("2026-08-03T10:15:30Z"));
        return e;
    }

    @Test
    void writesHeaderRow() {
        String csv = exporter.toCsv(List.of());

        assertThat(csv.lines().findFirst()).contains(
                "term,pos,ipa,meaning_vi,definition_en,cefr,band_level,tags,source_url,created_at");
    }

    @Test
    void writesOneRowPerEntry() {
        String csv = exporter.toCsv(List.of(
                entry("renewable", "tái tạo", List.of("environment")),
                entry("mitigate", "giảm nhẹ", List.of())));

        assertThat(csv.lines().count()).isEqualTo(3);   // header + 2 dòng
    }

    @Test
    void quotesFieldContainingComma() {
        String csv = exporter.toCsv(List.of(entry("renewable", "tái tạo, phục hồi", List.of())));

        assertThat(csv).contains("\"tái tạo, phục hồi\"");
    }

    @Test
    void escapesDoubleQuoteByDoubling() {
        String csv = exporter.toCsv(List.of(entry("renewable", "nghĩa \"đặc biệt\"", List.of())));

        assertThat(csv).contains("\"nghĩa \"\"đặc biệt\"\"\"");
    }

    @Test
    void quotesFieldContainingNewline() {
        String csv = exporter.toCsv(List.of(entry("renewable", "dòng một\ndòng hai", List.of())));

        assertThat(csv).contains("\"dòng một\ndòng hai\"");
    }

    @Test
    void joinsTagsWithSemicolon() {
        String csv = exporter.toCsv(List.of(entry("renewable", "tái tạo", List.of("a", "b"))));

        assertThat(csv).contains("a;b");
    }
}
