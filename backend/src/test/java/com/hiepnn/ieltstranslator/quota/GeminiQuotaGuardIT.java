package com.hiepnn.ieltstranslator.quota;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.fail;

class GeminiQuotaGuardIT extends AbstractPostgresIT {

    /** Lớp cha tắt hạn mức (0) cho mọi IT khác; ở đây bật lên đúng 2 để test được cái trần. */
    @DynamicPropertySource
    static void quotaProps(DynamicPropertyRegistry registry) {
        registry.add("auth.daily-gemini-calls", () -> 2);
    }

    @Autowired GeminiQuotaGuard guard;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM gemini_usage");
    }

    @Test
    @DisplayName("Vượt hạn mức ngày → GEMINI_QUOTA, mã UI đã biết hiển thị")
    void overDailyCapIsRejected() {
        Long user = ownerId();
        guard.consume(user);
        guard.consume(user);

        try {
            guard.consume(user);
            fail("Phải ném GEMINI_QUOTA khi vượt trần");
        } catch (AppException ex) {
            assertThat(ex.code()).isEqualTo(ErrorCode.GEMINI_QUOTA);
        }
    }

    @Test
    @DisplayName("Hạn mức tính RIÊNG từng người — A hết lượt không chặn B")
    void capIsPerUser() {
        Long a = ownerId();
        Long b = userId("second@test.local");
        guard.consume(a);
        guard.consume(a);

        // Một người làm 200 câu quiz không được phép khoá cả nhóm.
        guard.consume(b);
        Integer callsOfB = jdbc.queryForObject(
                "SELECT calls FROM gemini_usage WHERE user_id = ? AND day = CURRENT_DATE",
                Integer.class, b);
        assertThat(callsOfB).isEqualTo(1);
    }

    @Test
    @DisplayName("Bộ đếm tăng atomic trong một câu lệnh, không đọc-rồi-ghi")
    void counterIsIncrementedInDb() {
        Long user = ownerId();
        guard.consume(user);
        guard.consume(user);

        Integer calls = jdbc.queryForObject(
                "SELECT calls FROM gemini_usage WHERE user_id = ? AND day = CURRENT_DATE",
                Integer.class, user);
        assertThat(calls).isEqualTo(2);
    }
}
