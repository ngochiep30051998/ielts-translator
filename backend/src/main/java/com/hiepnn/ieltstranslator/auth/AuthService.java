package com.hiepnn.ieltstranslator.auth;

import com.hiepnn.ieltstranslator.auth.dto.AuthSessionDto;
import com.hiepnn.ieltstranslator.auth.dto.AuthUserDto;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Optional;

@Service
public class AuthService {

    private static final SecureRandom RANDOM = new SecureRandom();
    private static final int TOKEN_BYTES = 32;

    /**
     * Hạn phiên trượt theo mỗi lần dùng, nhưng chỉ GHI LẠI tối đa một lần mỗi ngày.
     *
     * <p>Không có ngưỡng này thì mọi request đều kéo theo một lượt UPDATE, biến bảng phiên
     * thành điểm nóng vì đúng một lý do làm đẹp.
     */
    private static final Duration TOUCH_INTERVAL = Duration.ofDays(1);

    private final AppUserRepository users;
    private final UserSessionRepository sessions;
    private final GoogleTokenClient google;
    private final AuthProperties props;

    public AuthService(AppUserRepository users, UserSessionRepository sessions,
                       GoogleTokenClient google, AuthProperties props) {
        this.users = users;
        this.sessions = sessions;
        this.google = google;
        this.props = props;
    }

    @Transactional
    public AuthSessionDto login(String code, String redirectUri) {
        // Chốt chặn redirect_uri nằm TRƯỚC khi chạm mạng: nhận đại chuỗi client gửi rồi
        // chuyển cho Google là cho một extension lạ mượn client_secret của mình.
        if (!expectedRedirectUri().equals(redirectUri)) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "redirect_uri không hợp lệ");
        }

        GoogleIdentity identity = google.exchange(code, redirectUri);

        // email_verified = false nghĩa là Google KHÔNG bảo đảm người này sở hữu hộp thư đó,
        // nên allowlist theo email mất sạch ý nghĩa.
        if (!identity.emailVerified()) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Email này chưa được Google xác minh");
        }
        if (!allowed(identity.email())) {
            throw AppException.of(ErrorCode.FORBIDDEN,
                    "Tài khoản này chưa được cấp quyền dùng hệ thống");
        }

        AppUser user = resolveUser(identity);
        String rawToken = newToken();
        UserSession session = new UserSession();
        session.setUser(user);
        session.setTokenHash(sha256(rawToken));
        session.setLastUsedAt(Instant.now());
        session.setExpiresAt(Instant.now().plus(props.sessionDays(), ChronoUnit.DAYS));
        sessions.save(session);

        return new AuthSessionDto(rawToken, session.getExpiresAt(), toDto(user));
    }

    /**
     * Khớp theo google_sub trước; không có thì theo email — đó là ca hàng do V6 tạo ra và
     * chưa ai đăng nhập, và cũng là lúc sổ từ cũ được nhận chủ.
     */
    private AppUser resolveUser(GoogleIdentity identity) {
        AppUser user = users.findByGoogleSub(identity.sub())
                .or(() -> users.findByEmailIgnoreCase(identity.email()))
                .orElseGet(AppUser::new);
        user.setGoogleSub(identity.sub());
        user.setEmail(identity.email());
        if (identity.name() != null) {
            user.setDisplayName(identity.name());
        }
        if (identity.picture() != null) {
            user.setPictureUrl(identity.picture());
        }
        user.setLastLoginAt(Instant.now());
        return users.save(user);
    }

    /**
     * Nhận diện user từ token. Trả Optional rỗng cho mọi ca hỏng — token rác, hết hạn, đã
     * thu hồi đều không phân biệt được với nhau từ phía người gọi, và cũng không nên.
     */
    @Transactional
    public Optional<Long> resolveUserId(String rawToken) {
        if (rawToken == null || rawToken.isBlank()) {
            return Optional.empty();
        }
        Instant now = Instant.now();
        return sessions.findAlive(sha256(rawToken), now).map(session -> {
            if (session.getLastUsedAt().isBefore(now.minus(TOUCH_INTERVAL))) {
                session.setLastUsedAt(now);
                session.setExpiresAt(now.plus(props.sessionDays(), ChronoUnit.DAYS));
            }
            return session.getUser().getId();
        });
    }

    /** Thu hồi ĐÚNG phiên đang dùng. Các thiết bị khác không bị đá ra. */
    @Transactional
    public void logout(String rawToken) {
        if (rawToken == null || rawToken.isBlank()) {
            return;
        }
        sessions.findAlive(sha256(rawToken), Instant.now())
                .ifPresent(session -> session.setRevokedAt(Instant.now()));
    }

    @Transactional(readOnly = true)
    public AuthUserDto me(Long userId) {
        return users.findById(userId).map(this::toDto)
                .orElseThrow(() -> AppException.of(ErrorCode.UNAUTHORIZED, "Phiên không còn hợp lệ"));
    }

    /** Dựng từ EXTENSION_ID phía server, KHÔNG nhận từ client. */
    public String expectedRedirectUri() {
        return "https://" + props.extensionId() + ".chromiumapp.org/";
    }

    /**
     * Danh sách rỗng = KHÓA HẾT, cố ý. Cấu hình thiếu phải làm hệ thống đóng lại chứ không
     * mở toang cho mọi tài khoản Google trên đời.
     */
    private boolean allowed(String email) {
        if (props.allowedEmails() == null || props.allowedEmails().isEmpty()) {
            return false;
        }
        String needle = email.toLowerCase(Locale.ROOT).trim();
        return props.allowedEmails().stream()
                .map(e -> e.toLowerCase(Locale.ROOT).trim())
                .anyMatch(needle::equals);
    }

    private AuthUserDto toDto(AppUser user) {
        return new AuthUserDto(user.getEmail(), user.getDisplayName(), user.getPictureUrl());
    }

    /** 32 byte ngẫu nhiên. Bản gốc trả cho client, DB chỉ giữ hash. */
    private String newToken() {
        byte[] bytes = new byte[TOKEN_BYTES];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String sha256(String raw) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(raw.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            // SHA-256 là thuật toán bắt buộc của mọi JVM; tới đây nghĩa là JVM hỏng.
            throw new IllegalStateException("JVM không có SHA-256", ex);
        }
    }
}
