package com.hiepnn.ieltstranslator.quota;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;

/**
 * Extends JpaRepository chỉ để có một repository interface hợp lệ cho Spring Data; nó không
 * dùng method kế thừa nào. Toàn bộ việc đếm nằm trong một câu native duy nhất.
 */
@Repository
public interface GeminiUsageRepository extends JpaRepository<GeminiUsage, GeminiUsage.Key> {

    /**
     * Tăng bộ đếm và trả về giá trị SAU khi tăng, trong đúng MỘT câu lệnh.
     *
     * <p>Đọc-rồi-ghi ở tầng Java sẽ hỏng thật: hai request song song cùng đọc ra một số rồi
     * cùng ghi đè, và hạn mức trở thành gợi ý. {@code ON CONFLICT ... RETURNING} thì atomic.
     */
    @Query(value = """
            INSERT INTO gemini_usage (user_id, day, calls) VALUES (:userId, :day, 1)
            ON CONFLICT (user_id, day) DO UPDATE SET calls = gemini_usage.calls + 1
            RETURNING calls
            """, nativeQuery = true)
    int incrementAndGet(@Param("userId") Long userId, @Param("day") LocalDate day);
}
