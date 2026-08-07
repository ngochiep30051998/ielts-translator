package com.hiepnn.ieltstranslator.srs;

import java.time.LocalDate;

/** Kết quả tính lịch cho một lượt review. Không chạm DB. */
public record Schedule(int intervalDays, double easeFactor, int repetitions,
                       int lapses, LocalDate dueDate, CardState state) {
}
