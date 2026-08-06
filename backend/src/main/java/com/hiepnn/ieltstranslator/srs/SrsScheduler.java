package com.hiepnn.ieltstranslator.srs;

import org.springframework.stereotype.Component;

import java.time.LocalDate;

/**
 * Công thức SM-2 rút gọn: chỉ interval theo ngày, không có learning steps trong ngày.
 *
 * <p>Hàm thuần — không đọc DB, không đọc đồng hồ hệ thống ({@code today} truyền vào).
 * Đây là điều kiện để test bằng bảng thuần tuý, và là lý do class này không giữ state.
 *
 * <p>ΔEF dùng đúng MỘT công thức cho cả bốn rating:
 * {@code 0.1 − (3−q)·(0.08 + (3−q)·0.02)} → AGAIN −0.32, HARD −0.14, GOOD 0, EASY +0.10.
 * Design gốc 2026-08-03 có ghi thêm "EF -= 0.2" ở dòng AGAIN; con số đó mâu thuẫn với
 * chính công thức bên dưới nó và đã bị loại trong spec Phase 2/3.
 */
@Component
public class SrsScheduler {

    private static final double MIN_EASE_FACTOR = 1.3;
    private static final double HARD_MULTIPLIER = 1.2;
    private static final double EASY_BONUS = 1.3;

    public Schedule next(SrsCard card, Rating rating, LocalDate today) {
        double easeFactor = Math.max(MIN_EASE_FACTOR, card.getEaseFactor() + easeDelta(rating));
        int repetitions = rating == Rating.AGAIN ? 0 : card.getRepetitions() + 1;
        int lapses = rating == Rating.AGAIN ? card.getLapses() + 1 : card.getLapses();
        CardState state = rating == Rating.AGAIN ? CardState.RELEARNING : CardState.REVIEW;
        int intervalDays = intervalFor(rating, card.getIntervalDays(), repetitions, easeFactor);

        return new Schedule(intervalDays, easeFactor, repetitions, lapses,
                today.plusDays(intervalDays), state);
    }

    private double easeDelta(Rating rating) {
        int diff = 3 - rating.q();
        return 0.1 - diff * (0.08 + diff * 0.02);
    }

    /** EF truyền vào đây là EF ĐÃ cập nhật, không phải EF cũ. */
    private int intervalFor(Rating rating, int currentInterval, int repetitions, double easeFactor) {
        if (rating == Rating.AGAIN) {
            return 1;
        }
        if (rating == Rating.HARD) {
            return atLeastOneDay(Math.round(currentInterval * HARD_MULTIPLIER));
        }

        long base = switch (repetitions) {
            case 1 -> 1L;
            case 2 -> 6L;
            default -> Math.round(currentInterval * easeFactor);
        };
        if (rating == Rating.EASY) {
            base = Math.round(base * EASY_BONUS);
        }
        return atLeastOneDay(base);
    }

    private int atLeastOneDay(long value) {
        return (int) Math.max(1L, value);
    }
}
