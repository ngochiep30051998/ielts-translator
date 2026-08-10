package com.hiepnn.ieltstranslator.quota;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;

import java.io.Serializable;
import java.time.LocalDate;

/**
 * Số lượt gọi Gemini của một người trong một ngày.
 *
 * <p>Tồn tại vì API key Gemini dùng CHUNG: một người làm 200 câu quiz là cả nhóm hết quota.
 * Entity này chỉ để {@code ddl-auto: validate} nhìn thấy bảng — mọi thao tác đi qua câu
 * native trong repository.
 */
@Entity
@Table(name = "gemini_usage")
@IdClass(GeminiUsage.Key.class)
public class GeminiUsage {

    @Id
    @Column(name = "user_id")
    private Long userId;

    @Id
    @Column(name = "day")
    private LocalDate day;

    @Column(name = "calls", nullable = false)
    private int calls;

    public Long getUserId() { return userId; }
    public LocalDate getDay() { return day; }
    public int getCalls() { return calls; }

    public static class Key implements Serializable {
        private Long userId;
        private LocalDate day;

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof Key other)) return false;
            return java.util.Objects.equals(userId, other.userId)
                    && java.util.Objects.equals(day, other.day);
        }

        @Override
        public int hashCode() { return java.util.Objects.hash(userId, day); }
    }
}
