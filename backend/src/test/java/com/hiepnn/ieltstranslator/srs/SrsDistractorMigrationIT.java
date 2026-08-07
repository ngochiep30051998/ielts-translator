package com.hiepnn.ieltstranslator.srs;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class SrsDistractorMigrationIT extends AbstractPostgresIT {

    @Autowired VocabEntryRepository vocab;
    @Autowired SrsDistractorRepository distractors;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM srs_distractor");
        jdbc.update("DELETE FROM vocab_entry");
    }

    private VocabEntry saveWord(String term) {
        VocabEntry entry = new VocabEntry();
        entry.setTerm(term);
        entry.setLemma(term);
        entry.setLang("en");
        entry.setPos("verb");
        entry.setMeaningVi("nghĩa của " + term);
        entry.setCollocations(objectMapper.createArrayNode());
        entry.setExamples(objectMapper.createArrayNode());
        return vocab.save(entry);
    }

    @Test
    @DisplayName("Lưu và đọc lại được hai mảng JSONB")
    void roundTripsJsonbColumns() {
        VocabEntry entry = saveWord("mitigate");

        SrsDistractor d = new SrsDistractor();
        d.setVocabEntry(entry);
        d.setViOptions(List.of("làm trầm trọng thêm", "phóng đại", "trì hoãn"));
        d.setEnOptions(List.of("aggravate", "exaggerate", "postpone"));
        d.setPromptVersion(1);
        distractors.save(d);

        SrsDistractor loaded = distractors.findByVocabEntry_Id(entry.getId()).orElseThrow();
        assertThat(loaded.getViOptions()).containsExactly("làm trầm trọng thêm", "phóng đại", "trì hoãn");
        assertThat(loaded.getEnOptions()).containsExactly("aggravate", "exaggerate", "postpone");
        assertThat(loaded.getPromptVersion()).isEqualTo(1);
    }

    @Test
    @DisplayName("Lọc theo promptVersion: bản ghi version cũ coi như không có")
    void filtersByPromptVersion() {
        VocabEntry entry = saveWord("resilient");
        SrsDistractor d = new SrsDistractor();
        d.setVocabEntry(entry);
        d.setViOptions(List.of("a", "b", "c"));
        d.setEnOptions(List.of("x", "y", "z"));
        d.setPromptVersion(1);
        distractors.save(d);

        assertThat(distractors.findByVocabEntry_IdInAndPromptVersion(List.of(entry.getId()), 1))
                .hasSize(1);
        assertThat(distractors.findByVocabEntry_IdInAndPromptVersion(List.of(entry.getId()), 2))
                .isEmpty();
    }

    @Test
    @DisplayName("Xoá từ trong sổ thì mồi nhử cascade theo, không để lại rác")
    void cascadesOnVocabDelete() {
        VocabEntry entry = saveWord("scrutinise");
        SrsDistractor d = new SrsDistractor();
        d.setVocabEntry(entry);
        d.setViOptions(List.of("a", "b", "c"));
        d.setEnOptions(List.of("x", "y", "z"));
        d.setPromptVersion(1);
        distractors.save(d);

        jdbc.update("DELETE FROM vocab_entry WHERE id = ?", entry.getId());

        assertThat(distractors.count()).isZero();
    }
}
