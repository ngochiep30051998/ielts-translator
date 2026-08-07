package com.hiepnn.ieltstranslator.srs;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class SrsSchedulerTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 8, 6);

    private final SrsScheduler scheduler = new SrsScheduler();

    private SrsCard card(double ease, int interval, int repetitions, int lapses, CardState state) {
        SrsCard c = new SrsCard();
        c.setEaseFactor(ease);
        c.setIntervalDays(interval);
        c.setRepetitions(repetitions);
        c.setLapses(lapses);
        c.setState(state);
        return c;
    }

    // ΔEF = 0.1 − (3−q)·(0.08 + (3−q)·0.02). Đây là bảng số chốt trong spec —
    // AGAIN là −0.32, KHÔNG phải −0.20 như design gốc 2026-08-03 viết nhầm.
    @ParameterizedTest
    @CsvSource({
            "AGAIN, 2.18",
            "HARD,  2.36",
            "GOOD,  2.50",
            "EASY,  2.60",
    })
    @DisplayName("ΔEF đúng cho từng rating, xuất phát từ EF mặc định 2.5")
    void easeFactorDelta(Rating rating, double expectedEase) {
        SrsCard c = card(2.5, 10, 5, 0, CardState.REVIEW);

        Schedule next = scheduler.next(c, rating, TODAY);

        assertThat(next.easeFactor()).isCloseTo(expectedEase, within(0.0001));
    }

    @Test
    @DisplayName("EF không bao giờ tụt dưới sàn 1.3 dù bấm Lại liên tục")
    void easeFactorFloor() {
        SrsCard c = card(1.4, 10, 5, 0, CardState.REVIEW);

        for (int i = 0; i < 10; i++) {
            Schedule next = scheduler.next(c, Rating.AGAIN, TODAY);
            c.setEaseFactor(next.easeFactor());
            c.setIntervalDays(next.intervalDays());
            c.setRepetitions(next.repetitions());
            c.setLapses(next.lapses());
        }

        assertThat(c.getEaseFactor()).isEqualTo(1.3);
    }

    @Test
    @DisplayName("Bấm Lại: interval về 1, repetitions về 0, lapses tăng, state RELEARNING")
    void again() {
        SrsCard c = card(2.5, 30, 4, 2, CardState.REVIEW);

        Schedule next = scheduler.next(c, Rating.AGAIN, TODAY);

        assertThat(next.intervalDays()).isEqualTo(1);
        assertThat(next.repetitions()).isZero();
        assertThat(next.lapses()).isEqualTo(3);
        assertThat(next.state()).isEqualTo(CardState.RELEARNING);
        assertThat(next.dueDate()).isEqualTo(TODAY.plusDays(1));
    }

    @Test
    @DisplayName("Bấm Khó: interval × 1.2, repetitions vẫn tăng, lapses không đổi")
    void hard() {
        SrsCard c = card(2.5, 10, 4, 2, CardState.REVIEW);

        Schedule next = scheduler.next(c, Rating.HARD, TODAY);

        assertThat(next.intervalDays()).isEqualTo(12);
        assertThat(next.repetitions()).isEqualTo(5);
        assertThat(next.lapses()).isEqualTo(2);
        assertThat(next.state()).isEqualTo(CardState.REVIEW);
    }

    @ParameterizedTest
    @CsvSource({
            // repetitions TRƯỚC khi review, interval trước, interval kỳ vọng sau khi bấm Tốt
            "0, 0,  1",     // thẻ mới → 1 ngày
            "1, 1,  6",     // lượt thứ hai → 6 ngày
            "2, 6, 15",     // lượt thứ ba trở đi → round(6 × 2.5)
    })
    @DisplayName("Bấm Tốt: 1 ngày → 6 ngày → nhân EF")
    void good(int repetitions, int interval, int expected) {
        SrsCard c = card(2.5, interval, repetitions,
                0, repetitions == 0 ? CardState.NEW : CardState.REVIEW);

        Schedule next = scheduler.next(c, Rating.GOOD, TODAY);

        assertThat(next.intervalDays()).isEqualTo(expected);
        assertThat(next.repetitions()).isEqualTo(repetitions + 1);
        assertThat(next.state()).isEqualTo(CardState.REVIEW);
    }

    @Test
    @DisplayName("Bấm Dễ trên thẻ đã ôn: nhân EF mới rồi nhân thêm 1.3")
    void easyOnReviewCard() {
        SrsCard c = card(2.5, 6, 2, 0, CardState.REVIEW);

        Schedule next = scheduler.next(c, Rating.EASY, TODAY);

        // EF mới = 2.6 → round(6 × 2.6) = 16 → round(16 × 1.3) = 21
        assertThat(next.easeFactor()).isCloseTo(2.6, within(0.0001));
        assertThat(next.intervalDays()).isEqualTo(21);
    }

    @Test
    @DisplayName("Bấm Dễ trên thẻ mới vẫn ra 1 ngày vì round(1 × 1.3) = 1 — đúng spec, không phải bug")
    void easyOnNewCard() {
        SrsCard c = card(2.5, 0, 0, 0, CardState.NEW);

        Schedule next = scheduler.next(c, Rating.EASY, TODAY);

        assertThat(next.intervalDays()).isEqualTo(1);
    }

    @Test
    @DisplayName("Interval không bao giờ nhỏ hơn 1 dù phép nhân làm tròn về 0")
    void intervalNeverZero() {
        SrsCard c = card(2.5, 0, 3, 0, CardState.NEW);

        Schedule next = scheduler.next(c, Rating.HARD, TODAY);

        assertThat(next.intervalDays()).isEqualTo(1);   // round(0 × 1.2) = 0 → nâng lên 1
    }

    @Test
    @DisplayName("Thẻ RELEARNING bấm Tốt quay lại REVIEW")
    void relearningRecovers() {
        SrsCard c = card(2.0, 1, 0, 1, CardState.RELEARNING);

        Schedule next = scheduler.next(c, Rating.GOOD, TODAY);

        assertThat(next.state()).isEqualTo(CardState.REVIEW);
        assertThat(next.intervalDays()).isEqualTo(1);   // repetitions về 1 → 1 ngày
    }
}
