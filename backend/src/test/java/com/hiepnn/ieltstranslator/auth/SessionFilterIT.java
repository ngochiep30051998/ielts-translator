package com.hiepnn.ieltstranslator.auth;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@AutoConfigureMockMvc
class SessionFilterIT extends AbstractPostgresIT {

    @Autowired MockMvc mockMvc;

    private String openSession(Instant expiresAt, Instant revokedAt) {
        String raw = "sf-" + System.nanoTime();
        UserSession session = new UserSession();
        session.setUser(ownerUser());
        session.setTokenHash(sha256(raw));
        session.setLastUsedAt(Instant.now());
        session.setExpiresAt(expiresAt);
        session.setRevokedAt(revokedAt);
        authSessions.save(session);
        return raw;
    }

    @Test
    @DisplayName("Thiếu header → 401 đúng hình dạng {code, message, retryable}")
    void missingHeaderIsUnauthorized() throws Exception {
        // Hình dạng lỗi quan trọng ngang status: UI phân nhánh theo `code`, và một trang
        // lỗi HTML từ tầng filter sẽ làm nó hiện "lỗi không xác định".
        mockMvc.perform(get("/api/vocab"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("UNAUTHORIZED"))
                .andExpect(jsonPath("$.message").isNotEmpty())
                .andExpect(jsonPath("$.retryable").value(false));
    }

    @Test
    @DisplayName("Token rác → 401")
    void garbageTokenIsUnauthorized() throws Exception {
        mockMvc.perform(get("/api/vocab").header("Authorization", "Bearer khong-phai-token"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("Header sai lược đồ (Basic) → 401, không nhận nhầm thành Bearer")
    void nonBearerSchemeIsUnauthorized() throws Exception {
        mockMvc.perform(get("/api/vocab").header("Authorization", "Basic " + IT_TOKEN))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("Token đã thu hồi → 401")
    void revokedTokenIsUnauthorized() throws Exception {
        String raw = openSession(Instant.now().plus(30, ChronoUnit.DAYS), Instant.now());
        mockMvc.perform(get("/api/vocab").header("Authorization", "Bearer " + raw))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("Token hết hạn → 401")
    void expiredTokenIsUnauthorized() throws Exception {
        String raw = openSession(Instant.now().minus(1, ChronoUnit.DAYS), null);
        mockMvc.perform(get("/api/vocab").header("Authorization", "Bearer " + raw))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("/api/health KHÔNG cần token — thứ dùng để chẩn đoán khi auth hỏng")
    void healthStaysPublic() throws Exception {
        // Bắt health đăng nhập là tự khoá mình ngoài cửa: đăng nhập hỏng thì không còn
        // endpoint nào nói được backend còn sống hay không.
        mockMvc.perform(get("/api/health")).andExpect(status().isOk());
    }

    @Test
    @DisplayName("Token hợp lệ đi lọt tới controller")
    void validTokenPasses() throws Exception {
        mockMvc.perform(get("/api/vocab").header("Authorization", BEARER_OWNER))
                .andExpect(status().isOk());
    }
}
