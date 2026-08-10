package com.hiepnn.ieltstranslator.srs;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.vocabulary.VocabService;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabRequest;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class SrsCardCreatorIT extends AbstractPostgresIT {

    @Autowired VocabService vocabService;
    @Autowired SrsCardRepository cards;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM vocab_entry");
    }

    private SaveVocabRequest request(String term, String pos) {
        return new SaveVocabRequest(term, term, "en", pos, null, "nghĩa của " + term,
                null, null, null, List.of(), null, null, null, null);
    }

    @Test
    @DisplayName("Lưu một từ đơn thì thẻ ôn tập được tạo ngay, due hôm nay, state NEW")
    void createsCardForWord() {
        SaveVocabResponse saved = vocabService.save(ownerId(), request("mitigate", "verb"));

        assertThat(cards.existsByVocabEntry_Id(saved.id())).isTrue();
        SrsCard card = cards.findAll().getFirst();
        assertThat(card.getState()).isEqualTo(CardState.NEW);
        assertThat(card.getDueDate()).isEqualTo(LocalDate.now());
        assertThat(card.getEaseFactor()).isEqualTo(2.5);
        assertThat(card.getRepetitions()).isZero();
    }

    @Test
    @DisplayName("Lưu cả một câu (pos = 'phrase') thì KHÔNG tạo thẻ — flashcard câu dài vô nghĩa")
    void skipsPhrase() {
        SaveVocabResponse saved = vocabService.save(ownerId(),
                request("Governments must act on climate change.", "phrase"));

        assertThat(cards.existsByVocabEntry_Id(saved.id())).isFalse();
        assertThat(cards.count()).isZero();
    }

    @Test
    @DisplayName("Lưu lại từ đã có không tạo thẻ thứ hai")
    void doesNotDuplicateOnResave() {
        vocabService.save(ownerId(), request("resilient", "adjective"));
        vocabService.save(ownerId(), request("resilient", "adjective"));

        assertThat(cards.count()).isEqualTo(1L);
    }
}
