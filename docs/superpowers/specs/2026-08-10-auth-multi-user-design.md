# Đăng nhập Google và tách dữ liệu theo người dùng

**Ngày:** 2026-08-10
**Trạng thái:** Design — CHỜ DUYỆT
**Phạm vi:** `backend/` + `extension/` + `docker-compose.yml` + `.env.example` + `README.md`.
Một migration Flyway `V6` có backfill. **Không thêm dependency Java nào.**

---

## 1. Vấn đề

Hệ thống hiện tại có đúng một người dùng, và điều đó nằm trong schema chứ không phải trong
giả định: `vocab_entry` ràng buộc `UNIQUE (term, pos)` toàn cục, `srs_card` `UNIQUE
(vocab_entry_id)`, không bảng nào có cột chủ sở hữu. Backend nghe ở `127.0.0.1:8080` và
`host_permissions` của extension ghim đúng địa chỉ đó.

Hệ quả thực tế: sổ từ vựng, lịch ôn SRS và lịch sử quiz sống trong volume `ielts_pgdata`
trên đúng một máy. Mở Chrome ở máy khác là bắt đầu lại từ số không. Đây không phải chuyện
thiếu tính năng đồng bộ — không có khái niệm "của ai" để mà đồng bộ.

## 2. Hành vi mới

**Lần đầu mở side panel trên một thiết bị:**

```
┌────────────────────────────────┐
│  IELTS Translator              │
│                                │
│  Đăng nhập để đồng bộ sổ từ    │
│  vựng giữa các thiết bị.       │
│                                │
│    [ Đăng nhập với Google ]    │
└────────────────────────────────┘
        ↓ bấm → cửa sổ Google
        ↓ chọn tài khoản
┌────────────────────────────────┐
│  hiepnn.office@gmail.com   [⏻] │
│  ─────────────────────────────  │
│  [Dịch] [Sổ từ] [Ôn] [Quiz]     │
└────────────────────────────────┘
```

Sau khi đăng nhập, mọi thứ chạy y như hiện tại — chỉ khác là dữ liệu gắn với tài khoản, nên
máy thứ hai đăng nhập cùng tài khoản thấy đúng sổ từ đó, đúng lịch ôn đó.

**Chưa đăng nhập:** panel chỉ hiện màn đăng nhập, không có tab nào. Bong bóng dịch trong
trang cũng báo "Cần đăng nhập" thay vì gọi API rồi nhận 401 — nói rõ nguyên nhân ngay chỗ
người dùng đang nhìn.

**Email không nằm trong danh sách cho phép:** đăng nhập Google thành công nhưng backend từ
chối với thông điệp riêng — "Tài khoản này chưa được cấp quyền dùng hệ thống." Phân biệt rõ
với lỗi mạng, vì đây là trạng thái vĩnh viễn, bấm lại không cứu được.

**Đăng xuất:** xoá token khỏi `chrome.storage.local` của **thiết bị đó** và thu hồi phiên ở
server. Các thiết bị khác vẫn đăng nhập bình thường.

## 3. Luồng OAuth — quyết định trung tâm

Extension **không bao giờ cầm `client_secret`**, và backend **không bao giờ tin một danh
tính do client tự khai**. Ba bước:

```
1. Extension: chrome.identity.launchWebAuthFlow(
     https://accounts.google.com/o/oauth2/v2/auth
       ?client_id=<WEB_CLIENT_ID>
       &response_type=code
       &scope=openid%20email%20profile
       &redirect_uri=https://<EXTENSION_ID>.chromiumapp.org/
       &state=<random>&nonce=<random>&prompt=select_account)
   → nhận về `code` trên URL redirect

2. Extension → backend:  POST /api/auth/google { code, redirectUri }

3. Backend → Google:     POST https://oauth2.googleapis.com/token
     code, client_id, CLIENT_SECRET, redirect_uri, grant_type=authorization_code
   → nhận { id_token, ... } và ĐỌC claim sub / email / email_verified
```

`redirect_uri` do client gửi lên **phải khớp chính xác** hằng số backend tự dựng từ
`EXTENSION_ID` — nhận đại chuỗi client gửi rồi chuyển thẳng cho Google là mở đường cho một
extension lạ mượn `client_secret` của mình.

**Vì sao backend đổi code chứ không phải extension.** Nếu extension tự đổi code lấy token
rồi gửi `id_token` lên, backend buộc phải verify chữ ký RS256 của Google — tức là tải JWKS,
cache, xoay khoá, kiểm `iss`/`aud`/`exp`/`nonce`. Đó là code bảo mật không nên tự viết, và
viết đúng thì phải thêm `nimbus-jose-jwt` hoặc cả `spring-boot-starter-oauth2-resource-server`
— vi phạm ràng buộc #12 vì một lợi ích không có thật.

Đổi ở backend thì ngược lại: token đi thẳng từ Google về server qua TLS, xác thực bằng
`client_secret`. Tài liệu OpenID Connect của Google nói đúng tình huống này — *"Since you are
communicating directly with Google over an intermediary-free HTTPS channel and using your
client secret to authenticate yourself to Google, you can be confident that the token you
receive really comes from Google and is valid."* Backend chỉ cần base64-decode phần payload
của `id_token` bằng `java.util.Base64` và đọc JSON bằng Jackson — **cả hai đã có sẵn**.

Kết quả: **không một dependency mới nào phía Java.** `RestClient` gọi Google đúng như
`GeminiClient` đang gọi Gemini.

> Cảnh báo phải giữ nguyên trong code: nếu sau này có ai đổi sang nhận `id_token` từ client,
> **bắt buộc** phải verify chữ ký. Miễn verify chỉ đúng khi token đến trực tiếp từ token
> endpoint.

### Vì sao `launchWebAuthFlow` chứ không `getAuthToken`

`chrome.identity.getAuthToken` gọn hơn (Chrome tự cache token) nhưng đòi **người dùng phải
đăng nhập vào chính Chrome**, chỉ chạy trên Chrome desktop bản Google, và cần một OAuth
client kiểu "Chrome Extension" gắn chặt vào extension ID. Nó cũng trả **access token**, không
trả `id_token` — muốn có danh tính vẫn phải gọi thêm userinfo endpoint.

`launchWebAuthFlow` không đòi đăng nhập Chrome, chạy trên mọi trình duyệt nhân Chromium, dùng
OAuth client kiểu "Web application", và cho phép đúng luồng authorization-code ở trên. Đổi
lại phải tự sinh `state`/`nonce` và tự bắt lỗi người dùng đóng cửa sổ.

## 4. Phiên đăng nhập: token mờ trong DB, không phải JWT

Sau bước 3, backend tạo phiên và trả về extension:

```json
{
  "token": "<43 ký tự base64url>",
  "expiresAt": "2026-10-09T04:00:00Z",
  "user": { "email": "hiepnn.office@gmail.com", "displayName": "Hiep Nguyen" }
}
```

Token là **32 byte ngẫu nhiên từ `SecureRandom`**, lưu trong DB dưới dạng **SHA-256 hash**
(cột `token_hash`), không lưu bản gốc. Mọi request sau đó mang `Authorization: Bearer <token>`.

**Vì sao không JWT tự ký.** JWT hấp dẫn vì không cần tra DB — nhưng ứng dụng này tra DB ở gần
như mọi endpoint rồi, nên "tiết kiệm một lượt đọc index" là lợi ích bằng không. Đổi lại JWT
mang theo hai thứ phiền: không thu hồi được trước hạn (đăng xuất ở máy mất cắp không có
nghĩa gì), và kéo theo một thư viện ký/verify. Token mờ tra DB thì đăng xuất là một dòng
`UPDATE`, và thu hồi toàn bộ phiên của một người là một dòng nữa.

**Hạn dùng:** 60 ngày, trượt — mỗi lần dùng thì gia hạn, nhưng **chỉ ghi DB tối đa một lần
mỗi ngày** cho mỗi phiên (so `last_used_at` trước khi update). Không có điều kiện đó thì mọi
request đều kéo theo một lượt ghi, biến bảng phiên thành điểm nóng vì đúng một lý do làm
đẹp.

**Không có refresh token.** Nó tồn tại để bù cho access token ngắn hạn của JWT; ở đây phiên
đã dài hạn và thu hồi được, thêm refresh token là thêm một vòng đời để sai.

## 5. Hợp đồng API

### `POST /api/auth/google` — công khai, không cần token

```json
{ "code": "4/0Ab...", "redirectUri": "https://<ext-id>.chromiumapp.org/" }
```

Trả `AuthSessionDto` như mục 4.

| tình huống | mã | HTTP |
|---|---|---|
| `code` sai / hết hạn / `redirectUri` không khớp | `UNAUTHORIZED` | 401 |
| Google trả `email_verified: false` | `UNAUTHORIZED` | 401 |
| email không nằm trong `AUTH_ALLOWED_EMAILS` | `FORBIDDEN` | 403 |
| Google token endpoint chết / timeout | `GEMINI_UNAVAILABLE` → **không dùng lại được** | — |

Google chết cần mã riêng: dùng `GEMINI_UNAVAILABLE` cho một dịch vụ không phải Gemini là nói
dối trong log. Thêm `AUTH_UNAVAILABLE` (503, `retryable: true`).

### `GET /api/auth/me` — cần token

Trả `{ email, displayName, pictureUrl }`. Đây là cách extension kiểm token còn sống sau khi
Chrome khởi động lại, thay vì đợi một request nghiệp vụ nào đó nhận 401.

### `POST /api/auth/logout` — cần token

Thu hồi đúng phiên đang dùng. Trả 204.

### Ba mã lỗi mới

`UNAUTHORIZED` (401), `FORBIDDEN` (403), `AUTH_UNAVAILABLE` (503). Thêm vào enum `ErrorCode`
buộc `GlobalExceptionHandler.statusFor()` phải có nhánh cho cả ba — switch ở đó exhaustive
và **không có `default`**, nên quên là fail compile chứ không phải fail lúc chạy. Đúng ràng
buộc #4.

### Mọi endpoint `/api/**` còn lại

Không đổi hình dạng request/response một chút nào. Chỉ thêm yêu cầu `Authorization`, và thiếu
nó thì trả `UNAUTHORIZED` theo đúng hình dạng `{code, message, retryable}` sẵn có. Ngoại lệ
duy nhất: `GET /api/health` vẫn công khai — nó là thứ dùng để chẩn đoán khi đăng nhập hỏng,
bắt nó đăng nhập là khoá mình ngoài cửa.

## 6. Backend

### Migration `V6__auth.sql`

```sql
CREATE TABLE app_user (
    id            BIGSERIAL PRIMARY KEY,
    google_sub    VARCHAR(64)  UNIQUE,          -- NULL cho tới lần đăng nhập đầu
    email         VARCHAR(320) NOT NULL UNIQUE,
    display_name  VARCHAR(200),
    picture_url   TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE user_session (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    token_hash   CHAR(64)    NOT NULL UNIQUE,   -- SHA-256 hex, KHÔNG phải token
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    revoked_at   TIMESTAMPTZ
);

-- Chủ sở hữu gắn ở ĐÚNG MỘT chỗ: vocab_entry. Mọi bảng khác treo vào nó.
ALTER TABLE vocab_entry ADD COLUMN user_id BIGINT REFERENCES app_user(id) ON DELETE CASCADE;

-- Backfill: tài khoản gốc lấy email từ placeholder Flyway (đọc từ .env).
INSERT INTO app_user (email, display_name)
VALUES ('${bootstrap_email}', 'Chủ sở hữu dữ liệu cũ')
ON CONFLICT (email) DO NOTHING;

UPDATE vocab_entry SET user_id = (SELECT id FROM app_user WHERE email = '${bootstrap_email}')
WHERE user_id IS NULL;

ALTER TABLE vocab_entry ALTER COLUMN user_id SET NOT NULL;

-- Ràng buộc cũ là toàn cục: hai người không được phép cùng lưu từ "mitigate".
ALTER TABLE vocab_entry DROP CONSTRAINT uq_vocab_term_pos;
ALTER TABLE vocab_entry ADD CONSTRAINT uq_vocab_user_term_pos UNIQUE (user_id, term, pos);
CREATE INDEX idx_vocab_user ON vocab_entry(user_id);
```

`${bootstrap_email}` là placeholder Flyway, nạp từ `AUTH_BOOTSTRAP_EMAIL` qua
`spring.flyway.placeholders.bootstrap_email`. Hàng `app_user` đó có `google_sub = NULL`; lần
đăng nhập đầu tiên khớp **theo email** rồi điền `google_sub` vào — sau đó mọi lần sau khớp
theo `google_sub`, vì email Google đổi được còn `sub` thì không.

> Rủi ro phải nói thẳng: ai đăng nhập đầu tiên bằng email đó sẽ nhận toàn bộ sổ từ hiện có.
> Chấp nhận được vì email đã được Google xác minh **và** phải nằm trong allowlist — hai lớp.

### Chủ sở hữu chỉ nằm ở `vocab_entry`

`srs_card`, `srs_distractor`, `quiz_item` đều đã có `vocab_entry_id`; `review_log` treo vào
`srs_card`, `quiz_attempt` treo vào `quiz_item`. Chủ sở hữu của chúng **suy ra được**, nên
thêm cột `user_id` vào từng bảng chỉ tạo cơ hội cho hai nguồn sự thật lệch nhau — mà lệch
kiểu này là dữ liệu người này lọt sang người kia, không có lỗi nào nổ ra.

Giá phải trả là mỗi truy vấn thêm một phép join tới `vocab_entry`. Các truy vấn đó **đã** join
sẵn rồi.

**`lookup_cache` cố ý KHÔNG có `user_id`.** Nó là cache bản dịch khoá theo
text+context+direction+mode+model+prompt version — dùng chung tiết kiệm quota Gemini thật sự,
và nội dung của nó là bản dịch của một chuỗi công khai, không phải dữ liệu cá nhân. Sổ từ mới
là thứ riêng tư, và nó nằm ở `vocab_entry`.

### Lấy user ra khỏi request

Một `OncePerRequestFilter` đọc header `Authorization`, hash token, tra `user_session`, kiểm
`revoked_at IS NULL AND expires_at > now()`, rồi đặt `userId` vào một `AuthContext` phạm vi
request. Không dùng `ThreadLocal` tự quản (dễ rò khi Tomcat tái dùng thread); dùng bean
`@RequestScope` để container tự dọn.

Controller nhận `AuthContext` qua constructor injection và truyền `userId` **tường minh**
xuống service. Không có `@AuthenticationPrincipal` ma thuật, đúng lối "không Lombok, không
magic" của repo.

### Chốt chặn không cho quên `user_id`

Đây là chỗ nguy hiểm nhất của cả thay đổi: quên một mệnh đề `WHERE user_id = ?` là người này
đọc được dữ liệu người kia, **im lặng**, và không test đơn lẻ nào bắt được vì mỗi test thường
chỉ có một user.

Chốt chặn là một IT riêng — `MultiUserIsolationIT` — dựng **hai** user có dữ liệu trùng tên
(cùng lưu từ `mitigate`), rồi với **mọi** endpoint `/api/**` khẳng định user A không bao giờ
thấy dữ liệu của B, và không sửa/xoá được dữ liệu của B. Endpoint mới không có mặt trong file
đó là endpoint chưa được chứng minh an toàn.

> Hướng đã cân nhắc và loại: Postgres Row-Level Security. Nó chặn ở tầng DB nên không thể
> quên được, mạnh hơn hẳn kỷ luật + test. Loại vì nó đòi `SET LOCAL app.user_id` đúng trong
> mọi transaction (kể cả job nền như `DistractorGenerator`), và một chỗ quên `SET` thì kết
> quả là **không thấy gì cả** — hỏng lặng lẽ theo chiều ngược lại. Với quy mô vài người quen,
> chi phí vận hành đó không đáng. Ghi lại ở đây để nếu số người dùng tăng thì biết đường quay
> lại.

### Hạn mức Gemini theo người dùng

Một API key Gemini dùng chung cho nhiều người: một người làm 200 câu quiz là cả nhóm hết
quota. Bảng `gemini_usage (user_id, day, calls)` với `UPSERT ... ON CONFLICT DO UPDATE`, chặn
ở `AUTH_DAILY_GEMINI_CALLS` (mặc định 300). Vượt thì trả `GEMINI_QUOTA` — mã đã có, UI đã
biết hiển thị.

## 7. Extension

**`manifest.config.ts`:**

- thêm permission `identity`
- `host_permissions` phải liệt kê **domain thật** (`https://ielts.<domain-cua-ban>/*`) cạnh
  `http://127.0.0.1:8080/*` cho dev. Đây là ràng buộc cứng: `backendUrl` trong Options là ô
  tự do, nhưng Chrome chỉ cho gọi những origin đã khai trong manifest. Trỏ Options sang một
  domain chưa khai = request chết im lặng. Ràng buộc #10 bây giờ có ba chỗ phải đồng bộ chứ
  không phải hai.

**`shared/messages.ts`** — ba luồng mới, đủ ba bước của ràng buộc #2:
`SIGN_IN` → `AuthUser`, `SIGN_OUT` → `null`, `GET_AUTH_STATE` → `AuthUser | null`.

`chrome.identity` chỉ gọi được từ service worker, nên toàn bộ luồng OAuth nằm ở đó — panel
chỉ gửi message. Ràng buộc #1 giữ nguyên và mạnh hơn: content script không những không gọi
HTTP, mà còn không bao giờ nhìn thấy token.

**Lưu token ở `chrome.storage.local`, KHÔNG phải `sync`.** `sync` sẽ đẩy token phiên sang mọi
profile Chrome đăng nhập cùng tài khoản Google — biến một phiên bị lộ thành tất cả. Đồng bộ
dữ liệu là việc của backend, không phải của storage.

**`api-client.ts`:** gắn `Authorization` vào mọi request; nhận 401 thì xoá token, phát
`AUTH_EXPIRED` để panel quay về màn đăng nhập. **Không tự đăng nhập lại ngầm** — `launchWebAuthFlow`
mở cửa sổ, tự mở khi người dùng không bấm gì là hành vi đáng ngờ.

**`App.tsx`:** thêm một trạng thái trước mọi tab — `loading` → `signed-out` → `signed-in`.
`loading` là bắt buộc: nhảy thẳng vào màn đăng nhập trong lúc còn đang đọc storage sẽ nháy một
cái ở mỗi lần mở panel.

**`badge.ts` / alarm:** chưa đăng nhập thì `refreshBadge` phải **không gọi API** và xoá số
trên badge. Không chặn thì cứ 30 phút lại một request 401, log rác và badge treo số cũ của
người dùng trước.

**`content/index.ts`:** chưa đăng nhập thì bong bóng hiện "Cần đăng nhập" kèm nút mở panel.

## 8. Triển khai VPS

`docker-compose.yml` thêm service `caddy` làm TLS terminator (Caddy tự xin và gia hạn Let's
Encrypt; nginx thì phải tự cắm certbot):

```
caddy  :443 → app:8080
app          (KHÔNG publish port ra host nữa)
db           (KHÔNG publish port ra host — đây là thay đổi bắt buộc)
```

`db` hiện đang publish `DB_PORT` ra host để chạy local. Trên VPS mà giữ nguyên là mở Postgres
ra Internet. Publish port phải nằm trong `docker-compose.override.yml` chỉ dùng ở máy dev.

**Biến môi trường mới** (vào cả `.env.example` **và** bảng trong `README.md` — ràng buộc #6):

| biến | ý nghĩa |
|---|---|
| `AUTH_GOOGLE_CLIENT_ID` | OAuth client kiểu Web application |
| `AUTH_GOOGLE_CLIENT_SECRET` | **chỉ ở backend**, không bao giờ vào extension |
| `AUTH_ALLOWED_EMAILS` | danh sách email được phép, ngăn cách bằng dấu phẩy |
| `AUTH_BOOTSTRAP_EMAIL` | chủ sở hữu dữ liệu cũ, dùng cho backfill V6 |
| `AUTH_SESSION_DAYS` | mặc định 60 |
| `AUTH_DAILY_GEMINI_CALLS` | mặc định 300 |
| `PUBLIC_ORIGIN` | domain thật, để dựng redirect URI và log |

**Backup.** Cảnh báo "không bao giờ `docker compose down -v`" trong CLAUDE.md từ chỗ làm mất
sổ từ của một người thành làm mất sổ từ của cả nhóm. Cần một cron `pg_dump` hàng ngày ra
ngoài volume trước khi đưa người thứ hai vào dùng.

## 9. Test

**Backend**

- `AuthControllerIT` — `@MockitoBean` cái `GoogleTokenClient` (đúng lối `QuizControllerIT` mock
  `GeminiClient`): code hợp lệ → có phiên; `email_verified: false` → 401; email ngoài
  allowlist → 403; Google chết → 503 `retryable: true`; `redirectUri` không khớp → 401
  **và không có call nào tới Google**.
- `SessionFilterIT` — thiếu header → 401; token rác → 401; token đã thu hồi → 401; token hết
  hạn → 401; `/api/health` không token → **200**.
- `MultiUserIsolationIT` — như mục 6, phủ mọi endpoint.
- `AuthMigrationIT` — dựng DB có sẵn `vocab_entry` **không** `user_id`, chạy V6, khẳng định
  mọi hàng đã có chủ và ràng buộc cũ đã đổi đúng. Đây là test duy nhất chứng minh dữ liệu
  hiện có của bạn không bốc hơi.
- `V6` chạy được **hai lần** không hỏng (Flyway không chạy lại, nhưng `AuthMigrationIT` phải
  chứng minh `ON CONFLICT DO NOTHING` đúng khi email đã tồn tại).

**Extension**

- `service-worker.test.ts` — `SIGN_IN` gọi `launchWebAuthFlow` rồi `POST /api/auth/google`;
  người dùng đóng cửa sổ → lỗi có hình dạng chuẩn, không ném thô.
- `api-client.test.ts` — mọi request có `Authorization`; 401 xoá token đúng một lần.
- `App.test.tsx` — chưa đăng nhập không render tab nào; `loading` không nháy màn đăng nhập.
- `badge.test.ts` — chưa đăng nhập thì không gọi API.

**Bằng chứng trước khi báo xong:** `mvn test`, `npm test`, `npm run build`.

## 10. Ngoài phạm vi

- Không có đăng ký tự phục vụ, không invite code — allowlist qua biến môi trường, đổi thì sửa
  `.env` và khởi động lại. Đúng mức cho "vài người quen".
- Không có trang admin, không đổi được allowlist khi đang chạy.
- Không có nhập/xuất dữ liệu giữa hai tài khoản (`GET /api/vocab/export.csv` vẫn còn, và giờ
  đã theo user).
- Không đồng bộ `Settings` của extension giữa các thiết bị — chúng là cấu hình cục bộ
  (giọng đọc, chế độ trigger), không phải dữ liệu học.
- Không có "đăng xuất mọi thiết bị" trên UI (câu SQL thì có sẵn).
- Không refresh token, không phiên ngắn hạn — xem mục 4.

## 11. Thứ tự làm và chỗ dễ vỡ

1. `V6` + `AuthMigrationIT` **trước tiên**, chạy trên bản sao dữ liệu thật. Mọi thứ khác vô
   nghĩa nếu bước này ăn mất sổ từ.
2. `/api/auth/google` + filter + `MultiUserIsolationIT`.
3. Scope lại từng repository theo `userId`, mỗi lần một feature (`vocabulary` → `srs` →
   `quiz`), mở rộng `MultiUserIsolationIT` sau mỗi bước.
4. Extension: auth state → gắn header → màn đăng nhập → badge/bubble.
5. Deploy: Caddy + domain + đăng ký redirect URI thật trên Google Cloud Console + đổi
   `host_permissions`.

**Chỗ dễ vỡ nhất, theo thứ tự:** (a) backfill V6 chạy sai trên DB thật; (b) một repository
method quên `userId` mà `MultiUserIsolationIT` chưa phủ; (c) `host_permissions` không khớp
domain thật nên extension chết im lặng sau khi deploy.

---

Sources:
- [chrome.identity API](https://developer.chrome.com/docs/extensions/reference/api/identity)
- [Google OpenID Connect — authorization code flow, token endpoint, ID token validation](https://developers.google.com/identity/openid-connect/openid-connect)
