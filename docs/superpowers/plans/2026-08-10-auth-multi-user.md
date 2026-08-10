# Đăng nhập Google và tách dữ liệu theo người dùng — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans để thực thi từng task. Các bước dùng cú pháp
> checkbox (`- [ ]`) để theo dõi.

**Goal:** Đăng nhập bằng Google, mọi dữ liệu học gắn với một tài khoản, dùng được trên nhiều
thiết bị. Sổ từ hiện có thuộc về tài khoản đầu tiên.

**Architecture:** Extension lấy `code` qua `chrome.identity.launchWebAuthFlow`; backend đổi
`code` với Google (có `client_secret`, TLS trực tiếp nên không phải verify chữ ký), tạo phiên
là token mờ 32 byte lưu hash trong `user_session`. Chủ sở hữu gắn ở **đúng một cột** —
`vocab_entry.user_id` — mọi bảng khác treo vào nó. **Không thêm dependency Java nào.**

**Tech Stack:** Spring Boot 3.4.1 / Java 21 / JPA / Flyway / Testcontainers + Mockito;
React 18 + TypeScript 5.7 + Vite + Vitest/RTL; Caddy cho TLS trên VPS.

**Spec:** `docs/superpowers/specs/2026-08-10-auth-multi-user-design.md`

---

## Trước khi bắt đầu — việc tay không code được

- [ ] **Google Cloud Console:** tạo OAuth client kiểu **Web application**. Authorized
      redirect URI: `https://<EXTENSION_ID>.chromiumapp.org/`. Lấy `client_id` + `client_secret`.
      (Extension ID cố định nhờ field `key` trong `manifest.config.ts` — đọc ID ở
      `chrome://extensions`.)
- [ ] **Sao lưu DB thật trước Task 1:**
      `docker compose exec db pg_dump -U ielts ielts > ~/ielts-backup-$(date +%F).sql`
      Task 1 sửa ràng buộc `UNIQUE` trên bảng chứa sổ từ của bạn. Không có bản sao lưu thì
      không chạy.

## Cấu trúc file

**Backend — tạo mới**

```
resources/db/migration/V6__auth.sql
auth/AppUser.java                    auth/AppUserRepository.java
auth/UserSession.java                auth/UserSessionRepository.java
auth/AuthService.java                auth/AuthController.java
auth/AuthContext.java                auth/SessionFilter.java
auth/GoogleTokenClient.java          auth/GoogleConfig.java
auth/GoogleIdentity.java             auth/AuthProperties.java
auth/dto/GoogleLoginRequest.java     auth/dto/AuthSessionDto.java
auth/dto/AuthUserDto.java
quota/GeminiUsage.java               quota/GeminiUsageRepository.java
quota/GeminiQuotaGuard.java
```

**Backend — sửa**

```
common/ErrorCode.java                common/GlobalExceptionHandler.java
common/AppException.java
vocabulary/{VocabEntry,VocabEntryRepository,VocabService,VocabController}.java
srs/{SrsCardRepository,SrsService,SrsController,ReviewLogRepository}.java
quiz/{QuizCandidateRepository,QuizItemRepository,QuizService,QuizController}.java
resources/application.yml
```

**Extension — sửa**

```
manifest.config.ts
src/shared/{types,messages,settings}.ts
src/background/{api-client,service-worker,badge}.ts
src/sidepanel/{App.tsx,styles.css}   + src/sidepanel/LoginScreen.tsx (mới)
src/content/index.ts
```

**Gốc repo — sửa:** `docker-compose.yml`, `.env.example`, `README.md`, `CLAUDE.md`

---

### Task 1: Migration V6 và backfill dữ liệu cũ

Task nguy hiểm nhất của cả kế hoạch, nên làm trước và làm một mình. Mọi thứ sau vô nghĩa nếu
bước này ăn mất sổ từ.

**Files:**
- Create: `backend/src/main/resources/db/migration/V6__auth.sql`
- Create: `backend/src/test/java/com/hiepnn/ieltstranslator/auth/AuthMigrationIT.java`
- Modify: `backend/src/main/resources/application.yml`

- [ ] **Step 1: Viết test thất bại — `AuthMigrationIT`**

```java
package com.hiepnn.ieltstranslator.auth;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Migration V6 đụng vào bảng chứa sổ từ THẬT của người dùng. Đây là test duy nhất chứng
 * minh dữ liệu cũ không bốc hơi và không đổi chủ.
 */
class AuthMigrationIT extends AbstractPostgresIT {

    @Autowired JdbcTemplate jdbc;

    private boolean constraintExists(String name) {
        Integer n = jdbc.queryForObject(
                "SELECT count(*) FROM pg_constraint WHERE conname = ?", Integer.class, name);
        return n != null && n > 0;
    }

    @Test
    @DisplayName("Ràng buộc UNIQUE cũ (toàn cục) đã bị thay bằng UNIQUE theo user")
    void uniqueConstraintIsNowPerUser() {
        // uq_vocab_term_pos toàn cục nghĩa là hai người không cùng lưu được từ "mitigate".
        assertThat(constraintExists("uq_vocab_term_pos")).isFalse();
        assertThat(constraintExists("uq_vocab_user_term_pos")).isTrue();
    }

    @Test
    @DisplayName("Tài khoản gốc được tạo với google_sub NULL — chờ lần đăng nhập đầu điền vào")
    void bootstrapUserExistsWithoutGoogleSub() {
        Integer n = jdbc.queryForObject(
                "SELECT count(*) FROM app_user WHERE google_sub IS NULL", Integer.class);
        assertThat(n).isEqualTo(1);
    }

    @Test
    @DisplayName("vocab_entry.user_id là NOT NULL — không có hàng nào vô chủ lọt qua")
    void vocabUserIdIsNotNullable() {
        String nullable = jdbc.queryForObject("""
                SELECT is_nullable FROM information_schema.columns
                WHERE table_name = 'vocab_entry' AND column_name = 'user_id'""", String.class);
        assertThat(nullable).isEqualTo("NO");
    }

    @Test
    @DisplayName("Xoá user thì sổ từ của user đó đi theo, không để lại hàng mồ côi")
    void deletingUserCascadesToVocab() {
        Long userId = jdbc.queryForObject("""
                INSERT INTO app_user (email, display_name) VALUES ('cascade@test.local', 'x')
                RETURNING id""", Long.class);
        jdbc.update("""
                INSERT INTO vocab_entry (term, lang, pos, meaning_vi, user_id)
                VALUES ('cascadeword', 'en', 'noun', 'x', ?)""", userId);

        jdbc.update("DELETE FROM app_user WHERE id = ?", userId);

        Integer left = jdbc.queryForObject(
                "SELECT count(*) FROM vocab_entry WHERE term = 'cascadeword'", Integer.class);
        assertThat(left).isZero();
    }
}
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=AuthMigrationIT
```

Expected: FAIL — `relation "app_user" does not exist`.

- [ ] **Step 3: Thêm placeholder Flyway vào `application.yml`**

Thay khối `flyway`:

```yaml
  flyway:
    enabled: true
    # Email chủ sở hữu dữ liệu cũ, dùng ở V6 để backfill vocab_entry.user_id.
    # KHÔNG có default trong file này: chạy migration với một email đoán bừa sẽ gán sổ từ
    # cho một tài khoản không ai đăng nhập được, và Flyway thì không chạy lại.
    placeholders:
      bootstrap_email: ${AUTH_BOOTSTRAP_EMAIL}
```

> Test dùng `AbstractPostgresIT` nên phải có giá trị lúc chạy test — thêm vào
> `@DynamicPropertySource` của `AbstractPostgresIT`:
> `registry.add("spring.flyway.placeholders.bootstrap_email", () -> "owner@test.local");`

- [ ] **Step 4: Tạo `V6__auth.sql`**

```sql
CREATE TABLE app_user (
    id            BIGSERIAL    PRIMARY KEY,
    -- NULL cho tới lần đăng nhập đầu tiên. Sau đó đây là khoá định danh THẬT: email Google
    -- đổi được, sub thì không.
    google_sub    VARCHAR(64)  UNIQUE,
    email         VARCHAR(320) NOT NULL UNIQUE,
    display_name  VARCHAR(200),
    picture_url   TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE user_session (
    id           BIGSERIAL   PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    -- SHA-256 hex của token, KHÔNG phải token. Lộ bảng này không cho phép mạo danh ai.
    token_hash   CHAR(64)    NOT NULL UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    revoked_at   TIMESTAMPTZ
);
CREATE INDEX idx_session_user ON user_session(user_id);

CREATE TABLE gemini_usage (
    user_id BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    day     DATE   NOT NULL,
    calls   INT    NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

-- Chủ sở hữu gắn ở ĐÚNG MỘT chỗ. srs_card / srs_distractor / quiz_item đã có
-- vocab_entry_id; review_log treo vào srs_card; quiz_attempt treo vào quiz_item. Nhân cột
-- user_id ra sáu bảng chỉ tạo cơ hội cho hai nguồn sự thật lệch nhau — mà lệch kiểu đó là
-- dữ liệu người này lọt sang người kia, không có lỗi nào nổ ra.
ALTER TABLE vocab_entry ADD COLUMN user_id BIGINT REFERENCES app_user(id) ON DELETE CASCADE;

INSERT INTO app_user (email, display_name)
VALUES ('${bootstrap_email}', 'Chủ sở hữu dữ liệu cũ')
ON CONFLICT (email) DO NOTHING;

UPDATE vocab_entry
SET user_id = (SELECT id FROM app_user WHERE email = '${bootstrap_email}')
WHERE user_id IS NULL;

ALTER TABLE vocab_entry ALTER COLUMN user_id SET NOT NULL;

-- Ràng buộc cũ TOÀN CỤC: hai người không được phép cùng lưu từ "mitigate".
ALTER TABLE vocab_entry DROP CONSTRAINT uq_vocab_term_pos;
ALTER TABLE vocab_entry ADD CONSTRAINT uq_vocab_user_term_pos UNIQUE (user_id, term, pos);
CREATE INDEX idx_vocab_user ON vocab_entry(user_id);
```

- [ ] **Step 5: Thêm `user` vào entity `VocabEntry`**

`ddl-auto: validate` sẽ fail nếu entity lệch schema (ràng buộc #8).

```java
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private AppUser user;
```

kèm getter/setter. (Task 2 tạo `AppUser`; làm Task 2 trước rồi quay lại step này nếu muốn
compile được từng bước — hoặc gộp hai task, nhưng đừng gộp migration với logic auth.)

- [ ] **Step 6: Chạy lại test**

```bash
cd backend && mvn test -Dtest=AuthMigrationIT
```

Expected: PASS — 4 test.

- [ ] **Step 7: Diễn tập trên bản sao dữ liệu THẬT**

```bash
# Dựng một DB tạm từ bản sao lưu, chạy app trỏ vào đó, xem Flyway có nuốt trôi không.
createdb ielts_rehearsal && psql ielts_rehearsal < ~/ielts-backup-*.sql
DB_NAME=ielts_rehearsal AUTH_BOOTSTRAP_EMAIL=<email-that-cua-ban> mvn spring-boot:run
psql ielts_rehearsal -c "SELECT count(*), count(user_id) FROM vocab_entry;"
```

Expected: hai số bằng nhau và bằng số từ bạn đang có. Lệch một hàng cũng dừng lại.

- [ ] **Step 8: Commit**

```bash
git add backend/src/main/resources/db/migration/V6__auth.sql \
        backend/src/main/resources/application.yml \
        backend/src/test/java/com/hiepnn/ieltstranslator/auth/AuthMigrationIT.java \
        backend/src/test/java/com/hiepnn/ieltstranslator/AbstractPostgresIT.java
git commit -m "feat(be): schema đa người dùng và backfill dữ liệu cũ"
```

---

### Task 2: Ba mã lỗi mới

**Files:**
- Modify: `common/ErrorCode.java`, `common/GlobalExceptionHandler.java`, `common/AppException.java`
- Create: `backend/src/test/java/com/hiepnn/ieltstranslator/common/ErrorCodeMappingTest.java`

- [ ] **Step 1: Viết test thất bại**

```java
package com.hiepnn.ieltstranslator.common;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ErrorCodeMappingTest {

    @Test
    @DisplayName("AUTH_UNAVAILABLE retry được; UNAUTHORIZED và FORBIDDEN thì không")
    void retryableFlagPerCode() {
        // retryable KHÔNG phải chuyện thẩm mỹ: UI dùng nó để chọn giữa "thử lại sau ít
        // giây" và "đường này chết hẳn". Bảo người bị từ chối quyền hãy thử lại là chỉ sai
        // đường hồi phục.
        assertThat(AppException.of(ErrorCode.AUTH_UNAVAILABLE, "x").retryable()).isTrue();
        assertThat(AppException.of(ErrorCode.UNAUTHORIZED, "x").retryable()).isFalse();
        assertThat(AppException.of(ErrorCode.FORBIDDEN, "x").retryable()).isFalse();
    }
}
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=ErrorCodeMappingTest
```

Expected: FAIL — không compile, `ErrorCode.UNAUTHORIZED` chưa tồn tại.

- [ ] **Step 3: Thêm ba giá trị vào `ErrorCode`**

```java
public enum ErrorCode {
    GEMINI_QUOTA,
    GEMINI_UNAVAILABLE,
    PARSE_ERROR,
    TEXT_TOO_LONG,
    NOT_FOUND,
    /** Thiếu token, token rác, token hết hạn, hoặc code OAuth không đổi được. */
    UNAUTHORIZED,
    /** Đăng nhập Google thành công nhưng email không nằm trong allowlist. Vĩnh viễn. */
    FORBIDDEN,
    /** Google token endpoint chết. Dùng GEMINI_UNAVAILABLE ở đây là nói dối trong log. */
    AUTH_UNAVAILABLE,
    INTERNAL
}
```

- [ ] **Step 4: Sửa `AppException.of`**

```java
    public static AppException of(ErrorCode code, String message) {
        // Retry được = "cùng request đó, lát nữa có thể thành công". UNAUTHORIZED và
        // FORBIDDEN không thoả: phải đăng nhập lại hoặc phải được cấp quyền, cả hai đều là
        // hành động khác chứ không phải bấm lại.
        boolean retryable = code == ErrorCode.GEMINI_UNAVAILABLE
                || code == ErrorCode.AUTH_UNAVAILABLE;
        return new AppException(code, message, retryable);
    }
```

- [ ] **Step 5: Thêm nhánh vào `statusFor()`**

```java
            case UNAUTHORIZED -> HttpStatus.UNAUTHORIZED;
            case FORBIDDEN -> HttpStatus.FORBIDDEN;
            case AUTH_UNAVAILABLE -> HttpStatus.SERVICE_UNAVAILABLE;
```

> Switch ở đó exhaustive và **không có `default`** — bỏ qua step này thì fail compile ngay,
> đúng thiết kế của ràng buộc #4.

- [ ] **Step 6: Chạy lại test + toàn bộ**

```bash
cd backend && mvn test -Dtest=ErrorCodeMappingTest && mvn -q compile
```

- [ ] **Step 7: Commit**

```bash
git commit -am "feat(be): mã lỗi UNAUTHORIZED, FORBIDDEN, AUTH_UNAVAILABLE"
```

---

### Task 3: Entity và repository của auth

**Files:**
- Create: `auth/AppUser.java`, `auth/AppUserRepository.java`, `auth/UserSession.java`,
  `auth/UserSessionRepository.java`, `auth/AuthProperties.java`

- [ ] **Step 1: `AppUser.java`**

```java
package com.hiepnn.ieltstranslator.auth;

import jakarta.persistence.*;

import java.time.Instant;

@Entity
@Table(name = "app_user")
public class AppUser {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * NULL với hàng do V6 tạo ra và chưa ai đăng nhập. Lần đăng nhập đầu khớp theo EMAIL
     * rồi điền cột này; từ đó về sau khớp theo sub, vì email Google đổi được còn sub thì
     * không.
     */
    @Column(name = "google_sub", unique = true)
    private String googleSub;

    @Column(nullable = false, unique = true)
    private String email;

    @Column(name = "display_name")
    private String displayName;

    @Column(name = "picture_url")
    private String pictureUrl;

    @Column(name = "created_at", insertable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "last_login_at")
    private Instant lastLoginAt;

    // getter/setter thủ công — dự án không dùng Lombok.
}
```

- [ ] **Step 2: `UserSession.java`** — cùng lối, các cột theo `V6__auth.sql`.

- [ ] **Step 3: `AppUserRepository.java`**

```java
public interface AppUserRepository extends JpaRepository<AppUser, Long> {
    Optional<AppUser> findByGoogleSub(String googleSub);
    Optional<AppUser> findByEmailIgnoreCase(String email);
}
```

> `IgnoreCase` là bắt buộc: Google trả email chữ thường, nhưng `AUTH_BOOTSTRAP_EMAIL` do
> người gõ tay vào `.env` thì không chắc. Lệch hoa thường = tạo tài khoản thứ hai và sổ từ
> cũ nằm ở tài khoản không ai đăng nhập được.

- [ ] **Step 4: `UserSessionRepository.java`**

```java
public interface UserSessionRepository extends JpaRepository<UserSession, Long> {

    /**
     * Phiên còn sống. Ba điều kiện đi cùng nhau trong CÂU TRUY VẤN chứ không kiểm ở Java:
     * quên một cái ở tầng service là một token đã thu hồi vẫn dùng được.
     */
    @Query("""
            select s from UserSession s join fetch s.user
            where s.tokenHash = :hash and s.revokedAt is null and s.expiresAt > :now
            """)
    Optional<UserSession> findAlive(@Param("hash") String hash, @Param("now") Instant now);
}
```

- [ ] **Step 5: `AuthProperties.java`** — `@ConfigurationProperties("auth")`, record với
      `googleClientId`, `googleClientSecret`, `allowedEmails` (List<String>), `sessionDays`,
      `dailyGeminiCalls`, `extensionId`.

- [ ] **Step 6: `mvn -q compile` rồi commit**

```bash
git commit -am "feat(be): entity và repository cho tài khoản, phiên đăng nhập"
```

---

### Task 4: Đổi code với Google

**Files:**
- Create: `auth/GoogleTokenClient.java`, `auth/GoogleConfig.java`, `auth/GoogleIdentity.java`
- Create: `backend/src/test/java/com/hiepnn/ieltstranslator/auth/GoogleTokenClientTest.java`

- [ ] **Step 1: Viết test thất bại — WireMock**

Đây là chỗ **đúng** để dùng WireMock (khác `AuthControllerIT` ở Task 5): thứ đang test chính
là tầng HTTP, y như `GeminiClientTest`.

```java
    @Test
    @DisplayName("Đọc sub và email từ payload của id_token, không verify chữ ký")
    void parsesIdTokenPayload() {
        // Chữ ký "rác" là CỐ Ý: token đến thẳng từ token endpoint qua TLS có client_secret
        // nên theo tài liệu OIDC của Google không cần verify. Test này khoá chính hành vi
        // đó — nếu ai thêm bước verify vào, nó đỏ và buộc phải đọc lại spec mục 3.
        String payload = base64Url("""
                {"sub":"1234567890","email":"a@b.com","email_verified":true,"name":"A B"}""");
        stubToken("{\"id_token\":\"header." + payload + ".chu-ky-rac\"}");

        GoogleIdentity id = client.exchange("code-abc", REDIRECT_URI);

        assertThat(id.sub()).isEqualTo("1234567890");
        assertThat(id.email()).isEqualTo("a@b.com");
        assertThat(id.emailVerified()).isTrue();
    }

    @Test
    @DisplayName("Google trả 400 (code hết hạn) → UNAUTHORIZED, KHÔNG phải AUTH_UNAVAILABLE")
    void expiredCodeIsUnauthorized() { /* stub 400 → assertThatThrownBy ... UNAUTHORIZED */ }

    @Test
    @DisplayName("Google trả 500 / timeout → AUTH_UNAVAILABLE, retry được")
    void googleDownIsRetryable() { /* stub 503 → AUTH_UNAVAILABLE, retryable true */ }

    @Test
    @DisplayName("client_secret KHÔNG bao giờ lọt vào log hay message lỗi")
    void secretNeverLeaks() { /* bắt exception, assert message không chứa secret */ }
```

- [ ] **Step 2: Chạy để xác nhận đỏ** — `mvn test -Dtest=GoogleTokenClientTest`

- [ ] **Step 3: `GoogleIdentity.java`**

```java
/** Danh tính đã lấy được từ Google. Chỉ những field thực sự dùng tới. */
public record GoogleIdentity(String sub, String email, boolean emailVerified,
                             String name, String picture) {
}
```

- [ ] **Step 4: `GoogleConfig.java`** — một `RestClient` trỏ `https://oauth2.googleapis.com`,
      connect 5s / read 10s, dựng bằng `SimpleClientHttpRequestFactory` y hệt `GeminiConfig`.
      Base URL đọc từ `${auth.google-token-url:...}` để test WireMock trỏ vào được.

- [ ] **Step 5: `GoogleTokenClient.java`**

```java
    public GoogleIdentity exchange(String code, String redirectUri) {
        // redirectUri KHÔNG được lấy nguyên xi từ client. AuthService đã so nó với hằng số
        // dựng từ EXTENSION_ID trước khi gọi vào đây; nếu bỏ bước đó thì một extension lạ
        // mượn được client_secret của mình để đổi code của nó.
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("code", code);
        form.add("client_id", props.googleClientId());
        form.add("client_secret", props.googleClientSecret());
        form.add("redirect_uri", redirectUri);
        form.add("grant_type", "authorization_code");
        ...
        JsonNode body = /* POST /token */;
        String idToken = body.path("id_token").asText("");
        return parse(idToken);
    }

    /**
     * Đọc payload của JWT KHÔNG verify chữ ký.
     *
     * <p>Hợp lệ ĐÚNG trong tình huống này và không nơi nào khác: token vừa đi thẳng từ
     * token endpoint của Google về đây qua TLS, và mình đã tự xác thực với Google bằng
     * client_secret. Tài liệu OIDC của Google nói rõ chỗ này. Nếu sau này token đến từ
     * client thay vì từ token endpoint, PHẢI verify RS256 qua JWKS — lúc đó mới bàn tới
     * việc thêm thư viện.
     */
    private GoogleIdentity parse(String idToken) {
        String[] parts = idToken.split("\\.");
        if (parts.length != 3) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Google trả id_token không hợp lệ");
        }
        JsonNode claims = mapper.readTree(Base64.getUrlDecoder().decode(parts[1]));
        ...
    }
```

- [ ] **Step 6: Chạy test — PASS. Commit**

```bash
git commit -am "feat(be): đổi authorization code với Google"
```

---

### Task 5: `POST /api/auth/google`

**Files:**
- Create: `auth/AuthService.java`, `auth/AuthController.java`,
  `auth/dto/{GoogleLoginRequest,AuthSessionDto,AuthUserDto}.java`
- Create: `backend/src/test/java/com/hiepnn/ieltstranslator/auth/AuthControllerIT.java`

- [ ] **Step 1: Viết test thất bại**

`@MockitoBean GoogleTokenClient` — đúng lối `QuizControllerIT` mock `GeminiClient`.

```java
    @Test
    @DisplayName("Đăng nhập lần đầu bằng email bootstrap NHẬN LUÔN sổ từ cũ")
    void firstLoginClaimsLegacyData() throws Exception {
        seedLegacyWordOwnedByBootstrapUser("mitigate");
        when(google.exchange(any(), any()))
                .thenReturn(new GoogleIdentity("sub-1", "owner@test.local", true, "Owner", null));

        String token = login("code-1");

        // Không tạo tài khoản thứ hai, và sổ từ cũ hiện ra ngay.
        assertThat(countUsers()).isEqualTo(1);
        mockMvc.perform(get("/api/vocab").header("Authorization", "Bearer " + token))
                .andExpect(jsonPath("$.totalElements").value(1));
    }

    @Test
    @DisplayName("google_sub được điền vào hàng cũ, lần sau khớp theo sub chứ không theo email")
    void googleSubIsBackfilledOnFirstLogin() throws Exception { /* ... */ }

    @Test
    @DisplayName("email_verified = false → 401, KHÔNG tạo tài khoản")
    void unverifiedEmailRejected() throws Exception { /* ... assert countUsers() không tăng */ }

    @Test
    @DisplayName("Email ngoài allowlist → 403 FORBIDDEN, retryable = false")
    void emailOutsideAllowlistRejected() throws Exception { /* ... */ }

    @Test
    @DisplayName("redirectUri không khớp EXTENSION_ID → 401 và KHÔNG gọi Google")
    void mismatchedRedirectUriNeverReachesGoogle() throws Exception {
        // Chốt chặn phải nằm TRƯỚC lượt gọi Google: nhận đại redirect_uri của client rồi
        // chuyển cho Google là cho một extension lạ mượn client_secret của mình.
        mockMvc.perform(post("/api/auth/google").contentType(APPLICATION_JSON)
                        .content("""
                        {"code":"c","redirectUri":"https://ke-gian.chromiumapp.org/"}"""))
                .andExpect(status().isUnauthorized());
        verify(google, never()).exchange(any(), any());
    }

    @Test
    @DisplayName("Google chết → 503 AUTH_UNAVAILABLE, retryable = true")
    void googleDownIsRetryable() throws Exception { /* ... */ }

    @Test
    @DisplayName("Hai lần đăng nhập tạo HAI phiên — đăng xuất máy này không đá máy kia ra")
    void eachLoginCreatesItsOwnSession() throws Exception { /* ... đếm user_session = 2 */ }
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

- [ ] **Step 3: DTO**

```java
public record GoogleLoginRequest(@NotBlank String code, @NotBlank String redirectUri) {}
public record AuthUserDto(String email, String displayName, String pictureUrl) {}
public record AuthSessionDto(String token, Instant expiresAt, AuthUserDto user) {}
```

- [ ] **Step 4: `AuthService.login()`**

```java
    @Transactional
    public AuthSessionDto login(String code, String redirectUri) {
        // 1. Chốt chặn redirect_uri TRƯỚC khi chạm mạng.
        if (!expectedRedirectUri().equals(redirectUri)) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "redirect_uri không hợp lệ");
        }
        GoogleIdentity id = google.exchange(code, redirectUri);

        // 2. email_verified false = Google KHÔNG bảo đảm người này sở hữu hộp thư đó, nên
        //    allowlist theo email mất hết ý nghĩa.
        if (!id.emailVerified()) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Email chưa được Google xác minh");
        }
        if (!allowed(id.email())) {
            throw AppException.of(ErrorCode.FORBIDDEN,
                    "Tài khoản này chưa được cấp quyền dùng hệ thống");
        }

        // 3. Khớp theo sub trước; không có thì theo email (ca hàng do V6 tạo), rồi điền sub.
        AppUser user = users.findByGoogleSub(id.sub())
                .or(() -> users.findByEmailIgnoreCase(id.email()))
                .orElseGet(AppUser::new);
        user.setGoogleSub(id.sub());
        ...
        return new AuthSessionDto(rawToken, session.getExpiresAt(), toDto(user));
    }

    /** Dựng từ EXTENSION_ID chứ không nhận từ client. */
    private String expectedRedirectUri() {
        return "https://" + props.extensionId() + ".chromiumapp.org/";
    }
```

Sinh token:

```java
    private static final SecureRandom RANDOM = new SecureRandom();

    /** 32 byte ngẫu nhiên. Trả bản gốc cho client, lưu SHA-256 xuống DB. */
    private String newToken() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
```

- [ ] **Step 5: `AuthController`** — `@PostMapping("/google")` với `@Valid`.

- [ ] **Step 6: Chạy test — PASS. Commit**

```bash
git commit -am "feat(be): endpoint đăng nhập Google"
```

---

### Task 6: Filter phiên, `/api/auth/me`, `/api/auth/logout`

**Files:**
- Create: `auth/AuthContext.java`, `auth/SessionFilter.java`
- Create: `backend/src/test/java/com/hiepnn/ieltstranslator/auth/SessionFilterIT.java`
- Modify: `auth/AuthController.java`

- [ ] **Step 1: Viết test thất bại**

```java
    @Test @DisplayName("Thiếu header → 401 đúng hình dạng {code,message,retryable}")
    void missingHeaderIsUnauthorized() { /* ... */ }

    @Test @DisplayName("Token rác → 401")
    void garbageTokenIsUnauthorized() { /* ... */ }

    @Test @DisplayName("Token đã thu hồi → 401")
    void revokedTokenIsUnauthorized() { /* ... */ }

    @Test @DisplayName("Token hết hạn → 401")
    void expiredTokenIsUnauthorized() { /* ... */ }

    @Test
    @DisplayName("/api/health KHÔNG cần token — nó là thứ dùng để chẩn đoán khi auth hỏng")
    void healthStaysPublic() throws Exception {
        // Bắt health đăng nhập là tự khoá mình ngoài cửa: đăng nhập hỏng thì không còn
        // endpoint nào nói được backend còn sống hay không.
        mockMvc.perform(get("/api/health")).andExpect(status().isOk());
    }

    @Test
    @DisplayName("logout thu hồi ĐÚNG phiên đang dùng, phiên còn lại vẫn sống")
    void logoutRevokesOnlyCurrentSession() { /* ... */ }

    @Test
    @DisplayName("last_used_at chỉ ghi lại tối đa MỘT lần mỗi ngày cho một phiên")
    void slidingExpiryWritesAtMostOncePerDay() throws Exception {
        // Không có điều kiện này thì mọi request đều kéo theo một lượt UPDATE, biến bảng
        // phiên thành điểm nóng vì đúng một lý do làm đẹp.
        String token = login();
        callAnything(token); Instant first = lastUsedAt(token);
        callAnything(token); assertThat(lastUsedAt(token)).isEqualTo(first);
    }
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

- [ ] **Step 3: `AuthContext.java`**

```java
/**
 * User của request hiện tại. Bean @RequestScope chứ không phải ThreadLocal tự quản —
 * Tomcat tái dùng thread, và một ThreadLocal quên dọn là request sau đọc nhầm user của
 * request trước. Đó là lỗi rò dữ liệu giữa hai người, im lặng.
 */
@Component
@RequestScope
public class AuthContext {
    private Long userId;

    public Long requireUserId() {
        if (userId == null) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Cần đăng nhập");
        }
        return userId;
    }
    void set(Long userId) { this.userId = userId; }
}
```

- [ ] **Step 4: `SessionFilter.java`** — `OncePerRequestFilter`, bỏ qua `/api/auth/google` và
      `/api/health`, đọc `Authorization: Bearer`, hash SHA-256, `findAlive`, đặt vào
      `AuthContext`. Thiếu/hỏng thì **không** ném ở filter (ngoài phạm vi
      `@RestControllerAdvice`) mà để `requireUserId()` ném ở tầng controller/service —
      như vậy lỗi vẫn đi đúng một đường và giữ hình dạng `{code,message,retryable}`.

- [ ] **Step 5: `/api/auth/me` và `/api/auth/logout`**

- [ ] **Step 6: Chạy test — PASS. Commit**

```bash
git commit -am "feat(be): filter phiên đăng nhập, /auth/me và /auth/logout"
```

---

### Task 7: Chốt chặn cách ly — `MultiUserIsolationIT`

Viết **trước** khi scope repository, và để đỏ. Đây là lưới an toàn cho ba task sau; có nó
trước thì mỗi bước scope tiếp theo được chứng minh ngay, không phải tin lời hứa.

**Files:**
- Create: `backend/src/test/java/com/hiepnn/ieltstranslator/auth/MultiUserIsolationIT.java`

- [ ] **Step 1: Viết test**

```java
/**
 * Hai user, dữ liệu TRÙNG TÊN (cùng lưu từ "mitigate"). Trùng tên là cố ý: nó bắt được ca
 * truy vấn tìm theo term mà quên lọc user — thứ mà dữ liệu khác nhau sẽ giấu đi.
 *
 * <p>Endpoint mới KHÔNG có mặt trong file này là endpoint chưa được chứng minh an toàn.
 */
class MultiUserIsolationIT extends AbstractPostgresIT {

    @Test @DisplayName("GET /api/vocab chỉ trả sổ từ của chính mình")
    void vocabListIsScoped() { /* A thấy 1 từ, B thấy 1 từ, và không phải cùng một id */ }

    @Test @DisplayName("GET /api/vocab/{id} của người khác → 404, KHÔNG phải 403")
    void readingOthersEntryIsNotFound() {
        // 404 chứ không 403: 403 xác nhận "id này có tồn tại", tức là một kênh dò id.
    }

    @Test @DisplayName("DELETE /api/vocab/{id} của người khác → 404 và hàng đó VẪN CÒN")
    void deletingOthersEntryDoesNothing() { /* kiểm cả status LẪN dữ liệu còn nguyên */ }

    @Test @DisplayName("export.csv chỉ chứa từ của mình")
    void exportIsScoped() { /* ... */ }

    @Test @DisplayName("GET /api/srs/due và /stats chỉ đếm thẻ của mình")
    void srsIsScoped() { /* ... */ }

    @Test @DisplayName("POST /api/srs/review với cardId của người khác → 404, lịch KHÔNG đổi")
    void reviewingOthersCardIsRejected() { /* ... */ }

    @Test
    @DisplayName("POST /api/quiz/generate với vocabIds của người khác → không sinh đề nào")
    void generateWithForeignVocabIdsYieldsNothing() {
        // vocabIds đến THẲNG từ client. Đây là lỗ IDOR rõ nhất của cả hệ thống: đề sinh ra
        // sẽ chứa term và câu ví dụ từ sổ từ của người khác.
    }

    @Test @DisplayName("POST /api/quiz/answer với quizItemId của người khác → 404")
    void answeringOthersItemIsRejected() { /* ... */ }

    @Test
    @DisplayName("POST /api/quiz/explain với quizItemId của người khác → 404 và KHÔNG gọi Gemini")
    void explainingOthersItemIsRejected() {
        // /explain TIẾT LỘ ĐÁP ÁN. Rò ở đây vừa là rò dữ liệu vừa là đốt quota người khác.
    }

    @Test @DisplayName("Hai user cùng lưu 'mitigate' đều thành công — ràng buộc UNIQUE theo user")
    void sameTermForTwoUsersIsAllowed() { /* ... */ }

    @Test @DisplayName("lookup_cache CỐ Ý dùng chung — user B ăn cache của A và không lỗi")
    void lookupCacheIsSharedOnPurpose() {
        // Đây là bất biến ngược chiều mọi test còn lại, nên phải viết ra: cache bản dịch
        // dùng chung tiết kiệm quota Gemini thật, và nó không chứa gì riêng tư.
    }
}
```

- [ ] **Step 2: Chạy — hầu hết đỏ.** Ghi lại danh sách test đỏ; Task 8–10 làm xanh dần.

- [ ] **Step 3: Commit (test đỏ, có chủ ý)**

```bash
git commit -am "test(be): chốt chặn cách ly dữ liệu giữa hai người dùng (đang đỏ)"
```

---

### Task 8: Scope module `vocabulary`

**Files:**
- Modify: `vocabulary/{VocabEntryRepository,VocabService,VocabController}.java`

- [ ] **Step 1: Repository — thêm `userId` vào MỌI method**

```java
    Optional<VocabEntry> findByUser_IdAndTermAndPos(Long userId, String term, String pos);

    List<VocabEntry> findAllByUser_IdOrderByCreatedAtDesc(Long userId);
```

và thêm `AND user_id = :userId` vào **cả `value` lẫn `countQuery`** của `search`.

> Quên `countQuery` thì danh sách đúng nhưng `totalElements` đếm cả sổ từ người khác —
> phân trang sai và lộ kích thước dữ liệu của họ. Test `vocabListIsScoped` phải khẳng định
> **cả `totalElements`**, không chỉ nội dung trang.

- [ ] **Step 2: Service — nhận `userId` tường minh**

Mọi method public đổi chữ ký: `save(Long userId, ...)`, `search(Long userId, ...)`,
`findById(Long userId, Long id)`, `delete(Long userId, Long id)`, `exportCsv(Long userId)`.

> Truyền tường minh chứ không cho service tự đọc `AuthContext`: đọc ngầm làm service không
> gọi được từ ngữ cảnh không có request (job nền, test), và giấu mất chuyện "hàm này phụ
> thuộc vào người đang đăng nhập".

`findById` và `delete` **không** tra theo id rồi so chủ sở hữu sau — tra thẳng theo
`(userId, id)`, không khớp thì `NOT_FOUND`. Một bước, không có khe hở giữa đọc và kiểm.

- [ ] **Step 3: Controller — inject `AuthContext`, truyền `auth.requireUserId()`**

- [ ] **Step 4: `mvn test`** — nhóm test vocab trong `MultiUserIsolationIT` chuyển xanh.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(be): sổ từ vựng tách theo người dùng"
```

---

### Task 9: Scope module `srs`

**Files:**
- Modify: `srs/{SrsCardRepository,ReviewLogRepository,SrsService,SrsController}.java`

- [ ] **Step 1: Repository — thêm join tới `vocabEntry.user`**

```java
    @Query("""
            select c from SrsCard c join fetch c.vocabEntry v
            where v.user.id = :userId and c.state <> :newState and c.dueDate <= :today
            order by c.dueDate asc, c.id asc
            """)
    List<SrsCard> findDue(@Param("userId") Long userId, ...);
```

Tương tự `findNewCards`, `countDue`, và **`countByState` / `countLearned`** — hai method cuối
hiện là derived query không join được, phải đổi thành `@Query` tường minh.

> `existsByVocabEntry_Id` giữ nguyên: nó chỉ chạy sau khi `vocab_entry` đã được xác định chủ.

- [ ] **Step 2: `SrsService.review(userId, cardId, rating)`** — tra thẻ theo `(userId, cardId)`,
      không khớp → `NOT_FOUND`.

- [ ] **Step 3: `SrsCardCreator` và `DistractorGenerator` KHÔNG đổi.** Cả hai nhận
      `vocabEntryId` của một entry đã có chủ; thêm `userId` vào đó là thêm một tham số có thể
      truyền sai mà không mua được gì.

- [ ] **Step 4: `mvn test`. Commit**

```bash
git commit -am "feat(be): lịch ôn SRS tách theo người dùng"
```

---

### Task 10: Scope module `quiz` và bịt IDOR

**Files:**
- Modify: `quiz/{QuizCandidateRepository,QuizItemRepository,QuizService,QuizController}.java`

- [ ] **Step 1: `findCandidates(userId, limit)`** — thêm `AND v.user_id = :userId` vào native
      query.

- [ ] **Step 2: `findReusable(...)`** — thêm `and qi.vocabEntry.user.id = :userId`.

- [ ] **Step 3: Lọc `vocabIds` do client gửi lên**

```java
    // request.vocabIds() đến THẲNG từ client. Không lọc thì người dùng đặt tay id của
    // người khác vào và nhận về đề chứa term + câu ví dụ trong sổ từ của họ.
    List<Long> vocabIds = (request.vocabIds() != null && !request.vocabIds().isEmpty())
            ? vocab.filterOwnedIds(userId, request.vocabIds())
            : candidates.findCandidates(userId, request.count());
```

- [ ] **Step 4: `answer` và `explain`** — nạp `QuizItem` theo `(userId, quizItemId)`.
      `explain` đặc biệt: nó **tiết lộ đáp án**, nên rò ở đây vừa là rò dữ liệu vừa là đốt
      quota người khác. Chốt chặn phải nằm **trước** lượt gọi Gemini, cùng chỗ với chốt
      "chưa trả lời thì 404" đã có.

- [ ] **Step 5: `mvn test`** — toàn bộ `MultiUserIsolationIT` phải xanh. Còn một test đỏ là
      còn một đường rò.

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(be): quiz tách theo người dùng, chặn id của người khác"
```

---

### Task 11: Hạn mức Gemini theo người dùng

**Files:**
- Create: `quota/{GeminiUsage,GeminiUsageRepository,GeminiQuotaGuard}.java`
- Modify: các chỗ gọi `gemini.generateJson` ở `TranslationService`, `QuizGenerator`, `QuizService`

- [ ] **Step 1: Test**

```java
    @Test @DisplayName("Vượt hạn mức ngày → GEMINI_QUOTA 429, UI đã biết hiển thị mã này")
    void overDailyCapIsRejected() { /* ... */ }

    @Test @DisplayName("Hạn mức tính RIÊNG từng người — A hết quota không chặn B")
    void capIsPerUser() { /* ... */ }

    @Test @DisplayName("Cache hit KHÔNG tính vào hạn mức — nó không gọi Gemini")
    void cacheHitDoesNotCount() { /* ... */ }
```

- [ ] **Step 2: `GeminiQuotaGuard.consume(userId)`** — `INSERT ... ON CONFLICT (user_id, day)
      DO UPDATE SET calls = gemini_usage.calls + 1 RETURNING calls`, so với
      `auth.daily-gemini-calls`. Một câu SQL, không đọc-rồi-ghi (hai request song song sẽ
      cùng đọc ra một số và cùng ghi đè).

- [ ] **Step 3: Gọi guard ngay TRƯỚC mỗi `gemini.generateJson`, sau khi đã tra cache.**

- [ ] **Step 4: `mvn test`. Commit**

```bash
git commit -am "feat(be): hạn mức Gemini theo từng người dùng"
```

---

### Task 12: Hợp đồng phía extension

**Files:**
- Modify: `extension/src/shared/types.ts`, `extension/src/shared/messages.ts`

- [ ] **Step 1: `types.ts`**

```ts
/** Gương của AuthUserDto phía backend. */
export interface AuthUser {
  email: string;
  displayName: string | null;
  pictureUrl: string | null;
}
```

- [ ] **Step 2: `messages.ts` — ba luồng, đủ ba bước của ràng buộc #2**

```ts
/** Mở cửa sổ Google. CHỈ service worker gọi được chrome.identity, nên panel phải đi đường này. */
export interface SignInRequest { type: 'SIGN_IN'; }
export interface SignOutRequest { type: 'SIGN_OUT'; }
/**
 * Trả null khi chưa đăng nhập — đó KHÔNG phải lỗi, nên nó là `data: null` chứ không phải
 * `ok: false`. Panel phân biệt "chưa đăng nhập" với "backend chết" bằng đúng chỗ này.
 */
export interface GetAuthStateRequest { type: 'GET_AUTH_STATE'; }
```

thêm cả ba vào union `ExtensionRequest` **và** `ResponseMap`
(`SIGN_IN: AuthUser`, `SIGN_OUT: null`, `GET_AUTH_STATE: AuthUser | null`).

- [ ] **Step 3: `npm run build`** — `ResponseMap` phủ đủ union nên thiếu khoá là fail compile.

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(ext): hợp đồng message SIGN_IN / SIGN_OUT / GET_AUTH_STATE"
```

---

### Task 13: Lưu token và gắn header

**Files:**
- Create: `extension/src/shared/auth-storage.ts` (+ test)
- Modify: `extension/src/background/api-client.ts` (+ test)

- [ ] **Step 1: Viết test thất bại**

```ts
  it('token lưu ở storage.local, KHÔNG phải storage.sync', async () => {
    // sync đẩy token phiên sang mọi profile Chrome đăng nhập cùng tài khoản Google —
    // biến một phiên bị lộ thành tất cả. Đồng bộ dữ liệu là việc của backend.
    await saveToken('t-123', '2026-10-09T00:00:00Z');
    expect(chrome.storage.local.set).toHaveBeenCalled();
    expect(chrome.storage.sync.set).not.toHaveBeenCalled();
  });

  it('mọi request mang Authorization: Bearer', async () => { /* ... */ });

  it('không có token thì KHÔNG gọi fetch, ném UNAUTHORIZED tại chỗ', async () => {
    // Gọi rồi nhận 401 cũng ra kết quả đó nhưng tốn một vòng mạng và một dòng log rác
    // mỗi lần badge alarm chạy.
  });

  it('nhận 401 thì xoá token đúng MỘT lần dù nhiều request cùng hỏng', async () => { /* ... */ });

  it('/api/auth/google KHÔNG gắn Authorization — lúc đó chưa có token nào', async () => {});
```

- [ ] **Step 2: Chạy để xác nhận đỏ** — `npm test -- src/background/api-client.test.ts`

- [ ] **Step 3: `auth-storage.ts`** — `saveToken`, `loadToken`, `clearToken` trên
      `chrome.storage.local`. `vitest.setup.ts` đã stub `chrome.storage.local`; cần
      `chrome.storage.sync` để test trên khẳng định được thì **bổ sung vào chính stub đó**,
      đừng stub rải rác (quy ước test của repo).

- [ ] **Step 4: `api-client.ts`** — `request()` đọc token và gắn header; 401 → `clearToken()`
      + phát `AUTH_EXPIRED`. **Không tự đăng nhập lại ngầm**: `launchWebAuthFlow` mở cửa sổ,
      tự bật khi người dùng không bấm gì là hành vi đáng ngờ.

- [ ] **Step 5: `npm test` — PASS. Commit**

```bash
git commit -am "feat(ext): lưu token phiên và gắn Authorization vào mọi request"
```

---

### Task 14: Luồng OAuth trong service worker

**Files:**
- Modify: `extension/src/background/service-worker.ts` (+ test), `manifest.config.ts`

- [ ] **Step 1: Viết test thất bại**

```ts
  it('SIGN_IN mở launchWebAuthFlow rồi đổi code ở backend', async () => {
    identity.launchWebAuthFlow.mockResolvedValue(
      'https://ext-id.chromiumapp.org/?code=abc&state=S');
    api.googleLogin.mockResolvedValue({ token: 't', expiresAt: '...', user: USER });

    const response = await send({ type: 'SIGN_IN' });

    expect(api.googleLogin).toHaveBeenCalledWith(
      expect.objectContaining({ code: 'abc' }));
    expect(response).toMatchObject({ ok: true, data: USER });
  });

  it('state trả về khác state gửi đi → từ chối, KHÔNG đổi code', async () => {
    // state là thứ duy nhất phân biệt "Google vừa trả lời mình" với một redirect bị nhét
    // vào. Sinh ra mà không đối chiếu thì thà đừng sinh.
    expect(api.googleLogin).not.toHaveBeenCalled();
  });

  it('người dùng đóng cửa sổ → lỗi ĐÚNG hình dạng {code,message,retryable}, không ném thô', async () => {});

  it('URL redirect mang ?error=access_denied → thông điệp riêng, không phải "lỗi không xác định"', async () => {});

  it('SIGN_OUT gọi backend rồi xoá token DÙ backend lỗi', async () => {
    // Backend chết mà giữ token lại thì người dùng kẹt trong trạng thái "đã bấm đăng xuất
    // nhưng vẫn đang đăng nhập" — và trên máy mượn thì đó đúng là điều họ vừa cố tránh.
  });

  it('GET_AUTH_STATE chưa đăng nhập trả data: null chứ không phải ok: false', async () => {});
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

- [ ] **Step 3: `manifest.config.ts`**

```ts
  permissions: ['storage', 'sidePanel', 'tabs', 'alarms', 'identity'],
  host_permissions: [
    'http://127.0.0.1:8080/*',        // dev
    'https://ielts.<domain-cua-ban>/*',  // production — PHẢI khớp backendUrl trong Options
  ],
```

> Ràng buộc #10 bây giờ có **ba** chỗ phải đồng bộ: `host_permissions`, `backendUrl` mặc
> định trong `shared/settings.ts`, và domain thật trên VPS. Options là ô nhập tự do nhưng
> Chrome chỉ cho gọi origin đã khai trong manifest — trỏ sang domain chưa khai thì request
> chết **im lặng**, không có lỗi nào nổ ra.

- [ ] **Step 4: `signIn()` trong service worker**

```ts
async function signIn(): Promise<AuthUser> {
  const redirectUri = chrome.identity.getRedirectURL();
  const state = crypto.randomUUID();
  const nonce = crypto.randomUUID();

  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  url.searchParams.set('client_id', GOOGLE_CLIENT_ID);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('scope', 'openid email profile');
  url.searchParams.set('redirect_uri', redirectUri);
  url.searchParams.set('state', state);
  url.searchParams.set('nonce', nonce);
  // Không có select_account thì Chrome im lặng dùng lại tài khoản Google lần trước —
  // người có hai tài khoản không đổi được mà cũng không hiểu vì sao.
  url.searchParams.set('prompt', 'select_account');

  const redirect = await chrome.identity.launchWebAuthFlow({ url: url.toString(), interactive: true });
  ...
}
```

`GOOGLE_CLIENT_ID` là hằng số build-time (`import.meta.env.VITE_GOOGLE_CLIENT_ID`).
Client **id** công khai được — nhưng `client_secret` thì **tuyệt đối không** vào extension;
nó chỉ sống ở backend.

- [ ] **Step 5: `npm test` — PASS. Commit**

```bash
git commit -am "feat(ext): đăng nhập Google qua chrome.identity"
```

---

### Task 15: Màn đăng nhập và cổng chặn trong panel

**Files:**
- Create: `extension/src/sidepanel/LoginScreen.tsx` (+ test)
- Modify: `extension/src/sidepanel/App.tsx` (+ test), `styles.css`

- [ ] **Step 1: Viết test thất bại**

```tsx
  it('trong lúc đang đọc trạng thái thì KHÔNG hiện màn đăng nhập', async () => {
    // Nhảy thẳng vào màn đăng nhập rồi mới biết là đã đăng nhập sẽ nháy một cái ở MỖI lần
    // mở panel. Trạng thái `loading` tồn tại vì lý do đó.
  });

  it('chưa đăng nhập thì không render tab nào', async () => {});

  it('đăng nhập xong hiện đủ bốn tab và email của người dùng', async () => {});

  it('token hết hạn giữa chừng (AUTH_EXPIRED) đưa panel về màn đăng nhập', async () => {});

  it('lỗi FORBIDDEN hiện thông điệp riêng, KHÔNG mời thử lại', async () => {
    // FORBIDDEN là trạng thái vĩnh viễn — bấm lại mười lần vẫn thế. Mời thử lại ở đây là
    // chỉ sai đường hồi phục.
  });
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

- [ ] **Step 3: `LoginScreen.tsx`** — một nút, một dòng giải thích, chỗ hiện lỗi.

- [ ] **Step 4: `App.tsx`** — thêm `authState: 'loading' | AuthUser | null` trước mọi tab;
      header hiện email + nút đăng xuất; nghe `AUTH_EXPIRED`.

- [ ] **Step 5: `npm test && npm run build` — PASS. Commit**

```bash
git commit -am "feat(ext): màn đăng nhập và cổng chặn trong side panel"
```

---

### Task 16: Badge và bong bóng khi chưa đăng nhập

**Files:**
- Modify: `extension/src/background/badge.ts` (+ test), `extension/src/content/index.ts` (+ test)

- [ ] **Step 1: Viết test thất bại**

```ts
  it('chưa đăng nhập thì refreshBadge KHÔNG gọi API và xoá số trên badge', async () => {
    // Alarm chạy 30 phút một lần. Không chặn thì cứ 30 phút một request 401, log rác, và
    // badge treo số cũ — con số của NGƯỜI DÙNG TRƯỚC trên máy dùng chung.
    expect(source.srsStats).not.toHaveBeenCalled();
    expect(chrome.action.setBadgeText).toHaveBeenCalledWith({ text: '' });
  });

  it('bong bóng khi chưa đăng nhập hiện "Cần đăng nhập" kèm nút mở panel', async () => {
    // Gọi API rồi hiện "lỗi không xác định" là nói sai nguyên nhân ngay chỗ người dùng
    // đang nhìn.
  });
```

- [ ] **Step 2 → 4: cài đặt, chạy test, commit**

```bash
git commit -am "feat(ext): badge và bong bóng xử lý trạng thái chưa đăng nhập"
```

---

### Task 17: Cấu hình, triển khai VPS, tài liệu

**Files:**
- Modify: `docker-compose.yml`, `.env.example`, `README.md`, `CLAUDE.md`
- Create: `docker-compose.override.yml`, `Caddyfile`

- [ ] **Step 1: `.env.example` + bảng "Biến môi trường" trong `README.md`** (ràng buộc #6 —
      thiếu một trong hai chỗ là vi phạm)

```
AUTH_GOOGLE_CLIENT_ID=
AUTH_GOOGLE_CLIENT_SECRET=
AUTH_ALLOWED_EMAILS=ban@gmail.com,ban-cua-ban@gmail.com
AUTH_BOOTSTRAP_EMAIL=ban@gmail.com
AUTH_SESSION_DAYS=60
AUTH_DAILY_GEMINI_CALLS=300
PUBLIC_ORIGIN=https://ielts.<domain-cua-ban>
```

- [ ] **Step 2: `docker-compose.yml` — gỡ publish port của `db` và `app`**

```yaml
  db:
    # KHÔNG có khối `ports` ở đây nữa. Trên VPS, publish 5432 ra host là mở Postgres ra
    # Internet — bảng vocab_entry của cả nhóm nằm sau đúng một mật khẩu trong .env.
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]
    volumes: ["./Caddyfile:/etc/caddy/Caddyfile:ro", "caddy_data:/data"]
```

- [ ] **Step 3: `docker-compose.override.yml`** — chỉ dùng ở máy dev, publish lại
      `DB_PORT`/`APP_PORT`. Compose tự nạp file này khi có mặt; trên VPS thì không copy nó lên.

- [ ] **Step 4: `Caddyfile`**

```
ielts.<domain-cua-ban> {
    reverse_proxy app:8080
}
```

- [ ] **Step 5: `SERVER_ADDRESS`** phải là `0.0.0.0` trong container (mặc định `127.0.0.1`
      của `application.yml` sẽ chặn cả Caddy).

- [ ] **Step 6: Cập nhật `CLAUDE.md`**

- cảnh báo `docker compose down -v` từ "mất sổ từ của bạn" thành **"mất sổ từ của cả nhóm"**
- thêm ràng buộc mới: *"Mọi truy vấn chạm dữ liệu học PHẢI lọc theo `userId`.
  `MultiUserIsolationIT` là chốt chặn; endpoint mới không có mặt ở đó là chưa an toàn."*
- ghi rõ ràng buộc #10 nay có ba chỗ đồng bộ, không phải hai
- ghi `AUTH_GOOGLE_CLIENT_SECRET` không bao giờ được xuất hiện phía extension

- [ ] **Step 7: Cron sao lưu trên VPS**

```bash
0 3 * * * docker compose exec -T db pg_dump -U ielts ielts | gzip > /backup/ielts-$(date +\%F).sql.gz
```

Bắt buộc **trước khi** đưa người thứ hai vào dùng.

- [ ] **Step 8: Commit**

```bash
git commit -am "chore: triển khai VPS, biến môi trường auth, cập nhật tài liệu"
```

---

## Kiểm tra cuối

```bash
cd backend && mvn test        # cần Docker cho Testcontainers
cd extension && npm test
cd extension && npm run build # nơi DUY NHẤT chạy type check
```

**Kiểm tra thủ công — không lệnh nào thay được:**

1. Máy A: nạp lại extension → panel hiện màn đăng nhập → đăng nhập → **sổ từ cũ hiện đủ**.
2. Máy A: lưu một từ mới.
3. **Máy B** (Chrome profile khác): đăng nhập **cùng tài khoản** → thấy đúng từ vừa lưu ở
   bước 2. Đây là thứ mà cả tính năng này tồn tại vì nó.
4. Máy B: đăng xuất → máy A **vẫn** đăng nhập.
5. Đăng nhập bằng một Gmail **không** có trong `AUTH_ALLOWED_EMAILS` → thông điệp "chưa được
   cấp quyền", không mời thử lại.
6. `curl https://ielts.<domain>/api/health` → 200 **không cần token**.
7. `curl https://ielts.<domain>/api/vocab` → 401 đúng hình dạng `{code,message,retryable}`.
8. `psql -h <ip-vps> -U ielts` từ máy ngoài → **phải bị từ chối kết nối**.

## Rủi ro, theo thứ tự

1. **Backfill V6 sai trên DB thật.** Giảm bằng Task 1 Step 7 (diễn tập trên bản sao) và bản
   sao lưu bắt buộc. Flyway không chạy lại, nên sai là phải khôi phục từ dump.
2. **Một repository method quên `userId` mà `MultiUserIsolationIT` chưa phủ.** Đây là lỗi rò
   dữ liệu im lặng. Giảm bằng luật: endpoint mới phải có test trong file đó.
3. **`host_permissions` không khớp domain thật** — extension chết im lặng sau khi deploy.
   Kiểm ở bước thủ công 6–7 trước khi kết luận.
4. **`AUTH_BOOTSTRAP_EMAIL` lệch hoa thường so với email Google trả về** — sinh tài khoản thứ
   hai và sổ từ cũ nằm ở tài khoản không ai đăng nhập được. Giảm bằng
   `findByEmailIgnoreCase` (Task 3).

