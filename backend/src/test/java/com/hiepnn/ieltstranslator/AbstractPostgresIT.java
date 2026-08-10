package com.hiepnn.ieltstranslator;

import com.hiepnn.ieltstranslator.auth.AppUser;
import com.hiepnn.ieltstranslator.auth.AppUserRepository;
import com.hiepnn.ieltstranslator.auth.UserSession;
import com.hiepnn.ieltstranslator.auth.UserSessionRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.HexFormat;
import java.util.Locale;

@SpringBootTest
@Testcontainers
public abstract class AbstractPostgresIT {

    /**
     * Email của tài khoản mà migration V6 tạo ra và gán toàn bộ dữ liệu cũ cho.
     * Test một-người-dùng dùng chính tài khoản này qua {@link #ownerId()}.
     */
    public static final String OWNER_EMAIL = "owner@test.local";

    /**
     * Token cố định cho mọi IT một-người-dùng. Cố định chứ không sinh ngẫu nhiên để các IT
     * dùng MockMvc chỉ cần gắn hằng {@link #BEARER_OWNER} vào header, không phải thread một
     * biến qua từng helper.
     */
    public static final String IT_TOKEN = "it-token-owner";
    public static final String BEARER_OWNER = "Bearer " + IT_TOKEN;

    @ServiceConnection
    static final PostgreSQLContainer<?> POSTGRES =
            new PostgreSQLContainer<>("postgres:16-alpine");

    static {
        POSTGRES.start();   // dùng chung một container cho mọi test class
    }

    @Autowired protected AppUserRepository authUsers;
    @Autowired protected UserSessionRepository authSessions;

    @DynamicPropertySource
    static void defaultProps(DynamicPropertyRegistry registry) {
        registry.add("gemini.api-key", () -> "test-key");
        registry.add("gemini.retry-backoff-millis", () -> 10L);
        // Cổng chết trên loopback: mọi đường gọi Gemini KHÔNG được mock (ví dụ
        // DistractorGenerator chạy nền khi test lưu từ) sẽ bị connection refused ngay
        // lập tức, thay vì bay ra generativelanguage.googleapis.com thật bằng "test-key".
        // Không có test nào được phép phụ thuộc mạng; test cần Gemini thì @MockitoBean nó.
        registry.add("gemini.base-url", () -> "http://127.0.0.1:1");

        // V6 backfill vocab_entry.user_id theo placeholder này. Không có giá trị thì Flyway
        // không chạy được và MỌI IT chết ngay lúc dựng context.
        registry.add("spring.flyway.placeholders.bootstrap_email", () -> OWNER_EMAIL);

        registry.add("auth.extension-id", () -> "testextensionid");
        registry.add("auth.google-client-id", () -> "test-client-id");
        registry.add("auth.google-client-secret", () -> "test-client-secret");
        registry.add("auth.allowed-emails", () -> OWNER_EMAIL + ",second@test.local");
        // Tắt hạn mức trong test: nó không phải thứ đang được kiểm ở đây, và một test dài
        // vô tình chạm trần sẽ đỏ vì lý do chẳng liên quan gì tới nó.
        registry.add("auth.daily-gemini-calls", () -> 0);
    }

    /**
     * Mở sẵn phiên cho tài khoản gốc trước MỖI test.
     *
     * <p>Chạy TRƯỚC {@code @BeforeEach} của lớp con (JUnit gọi superclass trước), nên các
     * hàm clean() xoá vocab_entry/quiz_* không đụng tới phiên này. Idempotent vì
     * {@code token_hash} là UNIQUE — chèn lần hai sẽ nổ.
     */
    @org.junit.jupiter.api.BeforeEach
    void ensureOwnerSession() {
        if (authSessions.findAlive(sha256(IT_TOKEN), Instant.now()).isPresent()) {
            return;
        }
        UserSession session = new UserSession();
        session.setUser(authUsers.findById(ownerId()).orElseThrow());
        session.setTokenHash(sha256(IT_TOKEN));
        session.setLastUsedAt(Instant.now());
        session.setExpiresAt(Instant.now().plus(60, ChronoUnit.DAYS));
        authSessions.save(session);
    }

    /** Chủ sở hữu dưới dạng entity — để test dựng VocabEntry trực tiếp gán được user. */
    protected AppUser ownerUser() {
        return authUsers.findById(ownerId()).orElseThrow();
    }

    /** Tài khoản gốc do V6 tạo — chủ của mọi dữ liệu trong test một-người-dùng. */
    protected Long ownerId() {
        return authUsers.findByEmailIgnoreCase(OWNER_EMAIL)
                .orElseThrow(() -> new IllegalStateException(
                        "V6 chưa tạo tài khoản gốc — kiểm tra placeholder bootstrap_email"))
                .getId();
    }

    /** Tạo (hoặc lấy) một tài khoản theo email. Dùng để dựng ca hai người dùng. */
    protected Long userId(String email) {
        return authUsers.findByEmailIgnoreCase(email).orElseGet(() -> {
            AppUser user = new AppUser();
            user.setEmail(email.toLowerCase(Locale.ROOT));
            user.setGoogleSub("sub-" + email);
            user.setDisplayName(email);
            return authUsers.save(user);
        }).getId();
    }

    /**
     * Mở một phiên cho user và trả về token THÔ để gắn vào header Authorization.
     *
     * <p>Hash ở đây phải khớp bit-for-bit với AuthService.sha256 — hai chỗ tính hash khác
     * nhau thì mọi IT dùng MockMvc sẽ nhận 401 mà không nói được vì sao.
     */
    protected String tokenFor(Long userId) {
        String raw = "test-token-" + userId + "-" + System.nanoTime();
        UserSession session = new UserSession();
        session.setUser(authUsers.findById(userId).orElseThrow());
        session.setTokenHash(sha256(raw));
        session.setLastUsedAt(Instant.now());
        session.setExpiresAt(Instant.now().plus(60, ChronoUnit.DAYS));
        authSessions.save(session);
        return raw;
    }

    /** Token của tài khoản gốc. Đường ngắn nhất cho test một-người-dùng. */
    protected String ownerToken() {
        return tokenFor(ownerId());
    }

    protected static String sha256(String raw) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(raw.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("JVM không có SHA-256", ex);
        }
    }
}
