package com.hiepnn.ieltstranslator.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Đường đăng nhập. GoogleTokenClient bị {@code @MockitoBean} — đúng lối QuizControllerIT
 * mock GeminiClient; WireMock chỉ có chỗ ở GoogleTokenClientTest, nơi thứ đang test là
 * tầng HTTP.
 */
@AutoConfigureMockMvc
class AuthControllerIT extends AbstractPostgresIT {

    private static final String REDIRECT = "https://testextensionid.chromiumapp.org/";

    @Autowired MockMvc mockMvc;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    @MockitoBean GoogleTokenClient google;

    @BeforeEach
    void cleanExtras() {
        reset(google);
        jdbc.update("DELETE FROM vocab_entry WHERE term = 'legacyword'");
    }

    private ResultActions login(String code, String redirectUri) throws Exception {
        return mockMvc.perform(post("/api/auth/google")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"code\":\"%s\",\"redirectUri\":\"%s\"}"
                        .formatted(code, redirectUri)));
    }

    private String tokenFromLogin(String code) throws Exception {
        String body = login(code, REDIRECT).andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(body).get("token").asText();
    }

    private long countUsers() {
        Long n = jdbc.queryForObject("SELECT count(*) FROM app_user", Long.class);
        return n == null ? 0 : n;
    }

    @Test
    @DisplayName("Đăng nhập lần đầu bằng email bootstrap NHẬN LUÔN sổ từ cũ")
    void firstLoginClaimsLegacyData() throws Exception {
        // Hàng vocab cũ đã thuộc về tài khoản do V6 tạo (google_sub còn NULL).
        jdbc.update("""
                INSERT INTO vocab_entry (term, lang, pos, meaning_vi, user_id)
                VALUES ('legacyword', 'en', 'noun', 'từ cũ', ?)""", ownerId());
        long usersBefore = countUsers();
        when(google.exchange(any(), any()))
                .thenReturn(new GoogleIdentity("sub-owner", OWNER_EMAIL, true, "Owner", null));

        String token = tokenFromLogin("code-1");

        // KHÔNG tạo tài khoản thứ hai — nếu tạo, sổ từ cũ nằm ở tài khoản không ai vào được.
        assertThat(countUsers()).isEqualTo(usersBefore);
        mockMvc.perform(get("/api/vocab").param("q", "legacyword")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalElements").value(1));
    }

    @Test
    @DisplayName("google_sub được điền vào hàng cũ — lần sau khớp theo sub, không theo email")
    void googleSubIsBackfilledOnFirstLogin() throws Exception {
        when(google.exchange(any(), any()))
                .thenReturn(new GoogleIdentity("sub-owner", OWNER_EMAIL, true, "Owner", null));

        tokenFromLogin("code-1");

        assertThat(authUsers.findByGoogleSub("sub-owner")).isPresent();
    }

    @Test
    @DisplayName("email_verified = false → 401 và KHÔNG tạo tài khoản")
    void unverifiedEmailRejected() throws Exception {
        long before = countUsers();
        when(google.exchange(any(), any()))
                .thenReturn(new GoogleIdentity("sub-x", "unverified@test.local", false, "X", null));

        login("code-1", REDIRECT)
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("UNAUTHORIZED"))
                .andExpect(jsonPath("$.retryable").value(false));

        assertThat(countUsers()).isEqualTo(before);
    }

    @Test
    @DisplayName("Email ngoài allowlist → 403 FORBIDDEN, KHÔNG retry được")
    void emailOutsideAllowlistRejected() throws Exception {
        long before = countUsers();
        when(google.exchange(any(), any()))
                .thenReturn(new GoogleIdentity("sub-y", "nguoila@test.local", true, "Y", null));

        login("code-1", REDIRECT)
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("FORBIDDEN"))
                .andExpect(jsonPath("$.retryable").value(false));

        assertThat(countUsers()).isEqualTo(before);
    }

    @Test
    @DisplayName("redirectUri không khớp EXTENSION_ID → 401 và KHÔNG gọi Google")
    void mismatchedRedirectUriNeverReachesGoogle() throws Exception {
        login("code-1", "https://ke-gian.chromiumapp.org/")
                .andExpect(status().isUnauthorized());

        // Chốt chặn phải nằm TRƯỚC lượt gọi Google: nhận đại redirect_uri của client rồi
        // chuyển cho Google là cho một extension lạ mượn client_secret của mình.
        verify(google, never()).exchange(any(), any());
    }

    @Test
    @DisplayName("Google chết → 503 AUTH_UNAVAILABLE, retry được")
    void googleDownIsRetryable() throws Exception {
        when(google.exchange(any(), any()))
                .thenThrow(AppException.of(ErrorCode.AUTH_UNAVAILABLE, "Google đang không phản hồi"));

        login("code-1", REDIRECT)
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value("AUTH_UNAVAILABLE"))
                .andExpect(jsonPath("$.retryable").value(true));
    }

    @Test
    @DisplayName("Hai lần đăng nhập tạo HAI phiên — đăng xuất máy này không đá máy kia ra")
    void eachLoginCreatesItsOwnSession() throws Exception {
        when(google.exchange(any(), any()))
                .thenReturn(new GoogleIdentity("sub-owner", OWNER_EMAIL, true, "Owner", null));

        String first = tokenFromLogin("code-1");
        String second = tokenFromLogin("code-2");
        assertThat(first).isNotEqualTo(second);

        mockMvc.perform(post("/api/auth/logout").header("Authorization", "Bearer " + first))
                .andExpect(status().isNoContent());

        // Máy thứ nhất bị thu hồi, máy thứ hai vẫn vào được.
        mockMvc.perform(get("/api/auth/me").header("Authorization", "Bearer " + first))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/auth/me").header("Authorization", "Bearer " + second))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value(OWNER_EMAIL));
    }

    @Test
    @DisplayName("Token trả về KHÔNG được lưu thô — DB chỉ giữ SHA-256")
    void rawTokenIsNeverStored() throws Exception {
        when(google.exchange(any(), any()))
                .thenReturn(new GoogleIdentity("sub-owner", OWNER_EMAIL, true, "Owner", null));

        String token = tokenFromLogin("code-1");

        // Lộ bảng user_session không được phép cho ai mạo danh ai.
        Integer raw = jdbc.queryForObject(
                "SELECT count(*) FROM user_session WHERE token_hash = ?", Integer.class, token);
        assertThat(raw).isZero();
        Integer hashed = jdbc.queryForObject(
                "SELECT count(*) FROM user_session WHERE token_hash = ?", Integer.class,
                sha256(token));
        assertThat(hashed).isEqualTo(1);
    }
}
