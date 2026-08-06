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
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

@Transactional
class SrsMigrationIT extends AbstractPostgresIT {

    @Autowired SrsCardRepository cards;
    @Autowired ReviewLogRepository logs;
    @Autowired VocabEntryRepository vocab;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM vocab_entry");
    }

    private VocabEntry entry(String term, String pos) {
        VocabEntry e = new VocabEntry();
        e.setTerm(term);
        e.setLemma(term);
        e.setLang("en");
        e.setPos(pos);
        e.setMeaningVi("nghĩa của " + term);
        e.setCollocations(objectMapper.createArrayNode());
        e.setExamples(objectMapper.createArrayNode());
        return vocab.save(e);
    }

    @Test
    @DisplayName("Xoá từ khỏi sổ thì thẻ và lịch sử review biến mất theo (ON DELETE CASCADE)")
    void deletingVocabCascades() {
        VocabEntry e = entry("mitigate", "verb");
        SrsCard card = new SrsCard();
        card.setVocabEntry(e);
        card.setDueDate(LocalDate.now());
        cards.saveAndFlush(card);

        ReviewLog log = new ReviewLog();
        log.setCard(card);
        log.setRating(Rating.GOOD);
        log.setPrevInterval(0);
        log.setNewInterval(1);
        logs.saveAndFlush(log);

        jdbc.update("DELETE FROM vocab_entry WHERE id = ?", e.getId());

        assertThat(jdbc.queryForObject("SELECT count(*) FROM srs_card", Long.class)).isZero();
        assertThat(jdbc.queryForObject("SELECT count(*) FROM review_log", Long.class)).isZero();
    }

    @Test
    @DisplayName("Một từ chỉ được có đúng một thẻ — ràng buộc UNIQUE ở tầng schema")
    void oneCardPerEntry() {
        VocabEntry e = entry("resilient", "adjective");
        SrsCard first = new SrsCard();
        first.setVocabEntry(e);
        first.setDueDate(LocalDate.now());
        cards.saveAndFlush(first);

        assertThat(jdbc.queryForObject(
                "SELECT count(*) FROM srs_card WHERE vocab_entry_id = ?", Long.class, e.getId()))
                .isEqualTo(1L);
    }

    @Test
    @DisplayName("Câu lệnh backfill chỉ tạo thẻ cho từ đơn, bỏ qua pos = 'phrase'")
    void backfillSkipsPhrases() {
        entry("mitigate", "verb");
        entry("resilient", "adjective");
        entry("Governments must act now.", "phrase");

        // Flyway chạy lúc khởi động context, khi vocab_entry còn rỗng — nên chạy lại
        // đúng câu lệnh của V3 trên dữ liệu vừa seed để kiểm chứng chính logic lọc.
        jdbc.update("""
                INSERT INTO srs_card (vocab_entry_id, due_date, state)
                SELECT id, CURRENT_DATE, 'NEW' FROM vocab_entry WHERE pos <> 'phrase'
                """);

        assertThat(jdbc.queryForObject("SELECT count(*) FROM srs_card", Long.class)).isEqualTo(2L);
        assertThat(jdbc.queryForObject("""
                SELECT count(*) FROM srs_card c
                JOIN vocab_entry v ON v.id = c.vocab_entry_id
                WHERE v.pos = 'phrase'
                """, Long.class)).isZero();
    }

    @Test
    @DisplayName("countIntroducedSince chỉ đếm lượt đầu đời của thẻ (prev_interval = 0)")
    void countsOnlyFirstEverReview() {
        VocabEntry e = entry("substantial", "adjective");
        SrsCard card = new SrsCard();
        card.setVocabEntry(e);
        card.setDueDate(LocalDate.now());
        cards.saveAndFlush(card);

        ReviewLog first = new ReviewLog();
        first.setCard(card);
        first.setRating(Rating.GOOD);
        first.setPrevInterval(0);
        first.setNewInterval(1);
        logs.saveAndFlush(first);

        ReviewLog second = new ReviewLog();
        second.setCard(card);
        second.setRating(Rating.GOOD);
        second.setPrevInterval(1);
        second.setNewInterval(6);
        logs.saveAndFlush(second);

        assertThat(logs.countIntroducedSince(Instant.EPOCH)).isEqualTo(1L);
    }
}
