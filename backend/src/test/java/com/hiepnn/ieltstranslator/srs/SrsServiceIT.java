package com.hiepnn.ieltstranslator.srs;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.srs.dto.CardDto;
import com.hiepnn.ieltstranslator.srs.dto.ReviewResponse;
import com.hiepnn.ieltstranslator.srs.dto.SrsStatsDto;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SrsServiceIT extends AbstractPostgresIT {

    @Autowired SrsService srsService;
    @Autowired SrsCardRepository cards;
    @Autowired ReviewLogRepository logs;
    @Autowired VocabEntryRepository vocab;
    @Autowired SrsDistractorRepository distractors;
    @Autowired DistractorGenerator generator;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM srs_distractor");
        jdbc.update("DELETE FROM vocab_entry");
    }

    private SrsCard card(String term, CardState state, LocalDate due, int repetitions) {
        VocabEntry e = new VocabEntry();
        e.setTerm(term);
        e.setLemma(term);
        e.setLang("en");
        e.setPos("verb");
        e.setIpa("/test/");
        e.setMeaningVi("nghĩa của " + term);
        e.setCollocations(objectMapper.createArrayNode());
        e.setExamples(objectMapper.createArrayNode());
        vocab.saveAndFlush(e);

        SrsCard c = new SrsCard();
        c.setVocabEntry(e);
        c.setState(state);
        c.setDueDate(due);
        c.setRepetitions(repetitions);
        c.setIntervalDays(repetitions == 0 ? 0 : 6);
        return cards.saveAndFlush(c);
    }

    @Test
    @DisplayName("Hàng đợi gộp thẻ đến hạn rồi mới tới thẻ mới")
    void dueBeforeNew() {
        card("alpha", CardState.REVIEW, LocalDate.now().minusDays(1), 3);
        card("bravo", CardState.NEW, LocalDate.now(), 0);

        List<CardDto> queue = srsService.due(50, 30);

        assertThat(queue).hasSize(2);
        assertThat(queue.get(0).term()).isEqualTo("alpha");
        assertThat(queue.get(1).term()).isEqualTo("bravo");
        assertThat(queue.get(0).meaningVi()).isEqualTo("nghĩa của alpha");
    }

    @Test
    @DisplayName("Thẻ chưa tới hạn không nằm trong hàng đợi")
    void skipsNotYetDue() {
        card("later", CardState.REVIEW, LocalDate.now().plusDays(3), 2);

        assertThat(srsService.due(50, 30)).isEmpty();
    }

    @Test
    @DisplayName("Giới hạn từ mới chặn đúng số thẻ NEW, thẻ đến hạn không bị chặn")
    void newLimitAppliesOnlyToNewCards() {
        for (int i = 0; i < 5; i++) {
            card("new" + i, CardState.NEW, LocalDate.now(), 0);
        }
        for (int i = 0; i < 4; i++) {
            card("due" + i, CardState.REVIEW, LocalDate.now(), 3);
        }

        List<CardDto> queue = srsService.due(50, 2);

        assertThat(queue).hasSize(6);   // 4 đến hạn (không giới hạn) + 2 thẻ mới
        assertThat(queue.stream().filter(c -> c.state() == CardState.NEW)).hasSize(2);
    }

    @Test
    @DisplayName("Số từ mới đã học hôm nay bị trừ khỏi hạn mức còn lại")
    void newLimitCountsWhatWasAlreadyLearnedToday() {
        SrsCard learned = card("done", CardState.NEW, LocalDate.now(), 0);
        srsService.review(learned.getId(), Rating.GOOD);   // dùng hết 1 suất từ mới

        card("waiting", CardState.NEW, LocalDate.now(), 0);

        assertThat(srsService.due(50, 1)).isEmpty();
    }

    @Test
    @DisplayName("Review cập nhật thẻ, ghi review_log, trả lịch kế tiếp")
    void reviewUpdatesCardAndLogs() {
        SrsCard c = card("mitigate", CardState.NEW, LocalDate.now(), 0);

        ReviewResponse response = srsService.review(c.getId(), Rating.GOOD);

        assertThat(response.intervalDays()).isEqualTo(1);
        assertThat(response.nextDueDate()).isEqualTo(LocalDate.now().plusDays(1));

        SrsCard updated = cards.findById(c.getId()).orElseThrow();
        assertThat(updated.getState()).isEqualTo(CardState.REVIEW);
        assertThat(updated.getRepetitions()).isEqualTo(1);

        assertThat(logs.findAll()).singleElement().satisfies(log -> {
            assertThat(log.getPrevInterval()).isZero();
            assertThat(log.getNewInterval()).isEqualTo(1);
            assertThat(log.getRating()).isEqualTo(Rating.GOOD);
        });
    }

    @Test
    @DisplayName("Review thẻ không tồn tại ném NOT_FOUND")
    void reviewUnknownCard() {
        assertThatThrownBy(() -> srsService.review(999_999L, Rating.GOOD))
                .isInstanceOf(AppException.class)
                .hasMessageContaining("999999");
    }

    @Test
    @DisplayName("stats: dueCount khớp đúng độ dài hàng đợi người dùng sẽ thấy")
    void statsMatchesQueueLength() {
        for (int i = 0; i < 3; i++) {
            card("new" + i, CardState.NEW, LocalDate.now(), 0);
        }
        card("due0", CardState.REVIEW, LocalDate.now(), 4);

        SrsStatsDto stats = srsService.stats(2);

        assertThat(stats.dueCount()).isEqualTo(3L);      // 1 đến hạn + 2 thẻ mới được phép
        assertThat(stats.dueCount()).isEqualTo(srsService.due(50, 2).size());
        assertThat(stats.newCount()).isEqualTo(3L);
        assertThat(stats.learnedCount()).isEqualTo(1L);
    }

    @Test
    @DisplayName("dueCount đếm theo hạn, KHÔNG bị limit cắt — badge báo tổng nợ thật")
    void statsIgnoresLimit() {
        for (int i = 0; i < 5; i++) {
            card("due" + i, CardState.REVIEW, LocalDate.now(), 3);
        }

        // Ghim lại ranh giới của bất biến "dueCount == độ dài hàng đợi": nó chỉ đúng khi
        // limit CHƯA phải ràng buộc chặn. Vượt limit thì badge cố tình báo tổng nợ thật
        // (5) trong khi hàng đợi bị cắt còn 2 — nếu sau này ai đó "sửa" stats cho khớp
        // hàng đợi thì badge sẽ nói dối người dùng là họ chỉ còn 2 thẻ.
        assertThat(srsService.due(2, 0)).hasSize(2);
        assertThat(srsService.stats(0).dueCount()).isEqualTo(5L);
    }

    private void saveDistractor(SrsCard card, int promptVersion) {
        SrsDistractor d = new SrsDistractor();
        d.setVocabEntry(card.getVocabEntry());
        d.setViOptions(List.of("làm trầm trọng thêm", "phóng đại", "trì hoãn"));
        d.setEnOptions(List.of("aggravate", "exaggerate", "postpone"));
        d.setPromptVersion(promptVersion);
        distractors.saveAndFlush(d);
    }

    @Test
    @DisplayName("Mồi nhử đã sinh đi vào ĐÚNG mảng của nó — vi ra viDistractors, en ra enDistractors")
    void carriesDistractorsIntoTheMatchingArray() {
        // Ca rỗng ở SrsControllerIT không phân biệt được hai mảng bị map ngược nhau;
        // chỉ ca có dữ liệu thật mới ghim được chiều nào ra field nào.
        SrsCard c = card("mitigate", CardState.REVIEW, LocalDate.now(), 3);
        saveDistractor(c, generator.currentPromptVersion());

        CardDto dto = srsService.due(50, 30).getFirst();

        assertThat(dto.viDistractors())
                .containsExactly("làm trầm trọng thêm", "phóng đại", "trì hoãn");
        assertThat(dto.enDistractors())
                .containsExactly("aggravate", "exaggerate", "postpone");
    }

    @Test
    @DisplayName("Mồi nhử sinh bằng version prompt cũ coi như không có, trả mảng rỗng chứ không null")
    void ignoresDistractorsFromAnOlderPromptVersion() {
        SrsCard c = card("mitigate", CardState.REVIEW, LocalDate.now(), 3);
        saveDistractor(c, generator.currentPromptVersion() - 1);

        CardDto dto = srsService.due(50, 30).getFirst();

        assertThat(dto.viDistractors()).isEmpty();
        assertThat(dto.enDistractors()).isEmpty();
    }
}
