# Bản web/PWA — thiết kế

Ngày: 2026-08-13

Mục tiêu: dùng được IELTS Translator trên điện thoại, không cần cài extension. Cài được vào
màn hình chính, nhận text chia sẻ từ app khác, và xem lại sổ từ khi mất mạng.

Extension **không đổi hành vi**. Nó vẫn `launchWebAuthFlow` + Bearer token như hôm nay.

---

## 1. Phạm vi

Có trong phase này:

- 5 tab y như side panel: Dịch, Sổ từ, Ôn tập, Quiz, Thống kê.
- Cài vào màn hình chính (PWA installable, chạy standalone).
- Nhận text chia sẻ từ app khác trên Android (Web Share Target) → vào thẳng tab Dịch.
- Offline **chỉ đọc**: mất mạng vẫn mở được app và xem sổ từ / thống kê đã tải.

Không có trong phase này:

- Ôn tập offline rồi đồng bộ sau. Nó cần một tầng ghi thứ hai và một quy tắc phân xử khi hai
  thiết bị cùng ôn một thẻ — backend hiện không có khái niệm đó. Để phase sau.
- Dịch từ đoạn bôi đen trên trang web. Web không làm được; Share Target là thứ thay thế gần
  nhất trên mobile.
- iOS Share Target. Safari không hỗ trợ `share_target`. Trên iOS vẫn cài được vào màn hình
  chính và vẫn dán tay được.

---

## 2. Cấu trúc — npm workspaces

```
ielts-translator/
├── package.json                 MỚI  { "workspaces": ["packages/*", "apps/*"] }
├── packages/core/               MỚI  không biết mình chạy ở đâu
│   ├── src/
│   │   ├── types.ts             ← extension/src/shared/types.ts
│   │   ├── api-client.ts        ← extension/src/background/api-client.ts
│   │   ├── operations.ts        MỚI ← rút từ handle() của service-worker.ts
│   │   ├── ports.ts             MỚI
│   │   ├── messages.ts          ← shared/messages.ts, BỎ phần chrome.runtime
│   │   ├── mcq.ts heatmap.ts pagination.ts summary.ts text.ts speech.ts theme.ts
│   │   └── ui/                  ← 5 tab + PayloadViews + StatsCharts + LoginScreen + styles.css
│   └── package.json             name: "@ielts/core"
├── apps/extension/              ← extension/ hiện tại, đã rút ruột
└── apps/web/                    MỚI
```

`packages/core` không import `chrome.*` ở bất kỳ đâu. Đó là bất biến kiểm được bằng grep, và
sẽ có một test canh nó.

### 2.1 Ports

`packages/core/src/ports.ts` khai mọi thứ phụ thuộc môi trường:

| Port | Extension | Web |
|---|---|---|
| `TokenStore` | `chrome.storage.local` | không dùng — cookie httpOnly, trình duyệt tự gửi |
| `SettingsStore` | `chrome.storage.local` | `localStorage` |
| `SettingsWatcher` | `chrome.storage.onChanged` | `window` event `storage` |
| `AuthFlow` | `chrome.identity.launchWebAuthFlow` | `location.href = '/api/auth/google/start'` |
| `LastResultStore` | biến trong bộ nhớ (y như hôm nay) | `sessionStorage` |
| `VocabChangeHook` | `refreshBadge()` | no-op |
| `PanelOpener` | `chrome.sidePanel.open` | no-op |

`LastResultStore` là port chứ không phải biến toàn cục vì trên web, F5 sẽ mất kết quả vừa
dịch. Extension cài đặt bằng một biến in-memory nên hành vi không đổi một chút nào.

### 2.2 Đường dữ liệu

Union `ExtensionRequest` và `ResponseMap` giữ nguyên tên và nguyên hình dạng. Chỉ khác chỗ
thực thi:

```
Extension:  UI → sendToBackground → chrome.runtime → service-worker → operations → ApiClient
Web:        UI → sendToBackground → operations → ApiClient          (cùng tiến trình)
```

Ràng buộc #2 của CLAUDE.md giữ nguyên: luồng mới vẫn phải thêm interface request + vào union
+ vào `ResponseMap`. Ràng buộc #1 cũng giữ nguyên cho extension.

Trên web, `sendToBackground` bọc `operations` trong try/catch để trả về cùng hình dạng
`{ ok, data } | { ok, error }` — mọi caller không phân biệt được mình đang chạy ở đâu.

### 2.3 Transport — chỗ duy nhất UI chạm môi trường

5 tab hiện gọi `sendToBackground`, hàm này gọi thẳng `chrome.runtime.sendMessage`. Trong
core, `sendToBackground` giữ **nguyên thân hàm**, chỉ đổi lời gọi đó thành một transport
tiêm vào:

```ts
export interface Transport {
  send(request: ExtensionRequest): Promise<unknown>;
  /** Lỗi khi `send` ném. Mỗi surface có nguyên nhân và cách khắc phục khác nhau. */
  disconnectedError: ApiError;
}
```

- Extension: `send = chrome.runtime.sendMessage`, `disconnectedError` = thông điệp
  "Không liên lạc được với extension…" như hôm nay.
- Web: `send = operations(...)` cùng tiến trình, tự bắt lỗi và trả `{ ok: false, error }` —
  đúng như listener của service worker đang làm.

Transport nằm ở **đúng cùng tầng** với `chrome.runtime.sendMessage`, tức nó trả về object
`{ ok, data }` thô còn `sendToBackground` vẫn là chỗ bọc try/catch và kiểm hình dạng.

### 2.4 Chuyện phải chứng minh trước khi đi tiếp

Mốc trước khi đụng vào: **26 file test, 313 test xanh**, `npm run build` (gồm `tsc --noEmit`)
thành công.

Tiêu chí sau khi rút ruột:

- **Không xoá test nào, không đổi một assertion nào.** Số test ≥ 313.
- Test được phép đổi *seam giả lập*: 6 file test của side panel đang giả lập
  `chrome.runtime.sendMessage` (38 chỗ) sẽ giả lập transport thay thế — find-replace thuần,
  vì transport ở đúng cùng tầng.
- `Options.test.tsx` và `messages.test.ts` ở lại `apps/extension`, không đổi.
- `packages/core` (mã nguồn sản phẩm, không kể test setup) **không được có một chuỗi
  `chrome.` nào** — có test grep canh việc này.

Không đạt thì lùi lại, không viết web.

---

## 3. Đăng nhập web — cookie httpOnly, redirect server-side

### 3.1 Vì sao không dùng localStorage

Cùng origin cho phép cookie httpOnly. Với cookie, `code` và token phiên **không bao giờ chạm
JavaScript**, nên một lỗ XSS trên web không lấy được phiên. Đổi lại, cookie là *ambient
credential* — nó tự đi kèm mọi request, kể cả request do trang khác kích hoạt. Toàn bộ mục
3.4 tồn tại vì cái giá đó.

### 3.2 Hai endpoint mới

```
GET /api/auth/google/start
    → sinh state = secrets.token_urlsafe(32)
    → set cookie state (mục 3.3), Max-Age 600
    → 302 tới https://accounts.google.com/o/oauth2/v2/auth?...
      client_id, response_type=code, scope="openid email profile",
      redirect_uri=<web_redirect_uri()>, state, prompt=select_account

GET /api/auth/google/callback?code=&state=
    → kiểm state (mục 3.5)
    → AuthService.login_web(code)  — tái dùng service.py:69-92 nguyên vẹn
    → set cookie phiên, xoá cookie state
    → 302 tới "/"        ← chuỗi hằng, KHÔNG BAO GIỜ lấy từ tham số
```

`scope` bắt buộc có `openid`. Thiếu nó Google vẫn trả 200 nhưng không có `id_token`, và
`google.py:103` sẽ ném "Google không trả id_token" — thông điệp trỏ nhầm về phía Google
trong khi lỗi nằm ở chuỗi scope của mình.

### 3.3 Cookie

| | Tên | Thuộc tính |
|---|---|---|
| Phiên | `__Host-ielts_session` | `HttpOnly; Secure; SameSite=Lax; Path=/`, Max-Age = `AUTH_SESSION_DAYS` |
| State | `__Host-ielts_oauth_state` | `HttpOnly; Secure; SameSite=Lax; Path=/`, Max-Age = 600 |

Tiền tố `__Host-` là bắt buộc. Không có nó, bất kỳ subdomain nào của cùng registrable domain
đều ghi đè được cookie của domain cha — cookie không có tính toàn vẹn theo origin. Trên
`*.vercel.app` đó không phải rủi ro lý thuyết. `__Host-` đòi `Secure` + `Path=/` + **không**
có `Domain`, đúng bằng thứ mình muốn.

`SameSite` phải là **Lax, không phải Strict**, cho *cả hai* cookie:

- Cookie state: redirect từ `accounts.google.com` về callback là điều hướng cross-site.
  Strict = cookie không được gửi = **100% lượt đăng nhập hỏng**, và hỏng theo kiểu trông
  giống lỗi phía Google.
- Cookie phiên: nó được set trong response của callback rồi trình duyệt đi tiếp tới `/`.

Đây là chỗ mà bản năng "chọn cái chặt hơn cho an toàn" phá hỏng mọi thứ. Ghi lại ở đây để
lần sau không ai siết nhầm.

`Secure` **không được suy từ `request.url.scheme`**: `Dockerfile:27` chạy uvicorn không có
`--proxy-headers`, và không dòng nào trong app đọc `X-Forwarded-Proto`. Caddy terminate TLS
nên scheme mà app thấy luôn là `http`. Suy từ đó là lặng lẽ phát cookie không-Secure trên
production HTTPS.

Thay vào đó: config `AUTH_COOKIE_SECURE` kiểu **`str`** với ba giá trị `auto` | `true` |
`false`, mặc định `auto`. Khai `str` chứ không `bool | None` vì pydantic không coi chuỗi
rỗng là `None`, nên `AUTH_COOKIE_SECURE=` trong `.env` sẽ ném lỗi parse. `auto` = `True` trừ
khi host là `localhost`/`127.0.0.1`. Khi không Secure thì **bỏ tiền tố `__Host-`** (tiền tố
đó cấm cookie không-Secure) — tên cookie tính từ cờ, hai hằng số.

### 3.4 CSRF — chốt chặn là header bắt buộc, không phải SameSite

Chuyển sang cookie là mở CSRF cho **toàn bộ** API đang chạy. `SameSite=Lax` che POST/DELETE
nhưng **cố ý cho GET điều hướng đi qua**, và repo có endpoint GET gây tác dụng phụ thật:

- `GET /api/srs/due` (`srs/router.py:18`) và `GET /api/srs/practice` (`srs/router.py:47`)
  đều gọi `_request_missing` → `distractors.schedule(...)` → `db.commit()` + tới 10 lượt gọi
  Gemini, và đường đó **không đi qua quota guard**.
- `GET /api/vocab/export.csv` (`vocabulary/router.py:51`) kích hoạt được bằng điều hướng.

**Quy tắc: token đọc từ cookie CHỈ được chấp nhận khi request mang header `X-IELTS-Web: 1`.**

Điều hướng top-level không đặt được header. Fetch cross-site mang header lạ thì kích hoạt
preflight, mà CORS chỉ mở cho `chrome-extension://<id>` nên preflight bị từ chối. Đây là
chốt chặn đầy đủ, không phụ thuộc trình duyệt, không thêm dependency, và không cần mã lỗi
mới — thiếu header thì coi như chưa đăng nhập, trả 401 y như hôm nay.

`SameSite=Lax` vẫn giữ, làm lớp thứ hai.

Hệ quả với `export.csv`: SPA phải tải bằng `fetch` kèm header rồi tạo blob download, không
được dùng `<a href>` hay `location.href`.

Đường Bearer **không** chịu quy tắc này — nó miễn nhiễm CSRF theo thiết kế, và extension
không gửi header đó.

### 3.5 So state cho đúng

```python
# SAI — cả hai cùng vắng thì None == None → True → gate mở toang
if state != request.cookies.get(STATE_COOKIE): raise ...
```

Đúng: bắt buộc **cả hai tồn tại và khác rỗng**, chặn ký tự ngoài ASCII trước khi so
(`secrets.compare_digest` ném `TypeError` với non-ASCII, mà `state` do client điều khiển
hoàn toàn — `?state=é` sẽ biến 401 thành 500), rồi `secrets.compare_digest`.

`delete_cookie` phải truyền đúng `path` đã dùng lúc set, nếu không trình duyệt coi là cookie
khác và không xoá gì cả.

### 3.6 Gate redirect_uri — tách hai hàm, không nới thành danh sách

`expected_redirect_uri()` hiện là gate duy nhất ở `service.py:66`. **Không** nới nó thành một
tập chung: làm thế thì `POST /api/auth/google` — endpoint trả token phiên **thô trong JSON
body** — sẽ chấp nhận luôn redirect_uri của web callback, và hai luồng mượn được của nhau.

Tách thành hai hàm dựng-từ-server riêng, mỗi luồng so chuỗi chính xác với đúng một giá trị:

```python
def extension_redirect_uri(self) -> str:      # chỉ POST /api/auth/google dùng
    return f"https://{self._settings.extension_id}.chromiumapp.org/"

def web_redirect_uri(self) -> str:            # chỉ callback dùng, KHÔNG nhận từ client
    return f"{self._settings.web_base_url}/api/auth/google/callback"
```

`WEB_BASE_URL` rỗng phải làm `/api/auth/google/start` **fail closed** với thông điệp cấu
hình rõ ràng. Đây là bẫy đã có sẵn: `EXTENSION_ID` rỗng sinh ra `https://.chromiumapp.org/`
— một chuỗi hợp lệ về cú pháp, nên cấu hình thiếu không nổ, chỉ làm mọi lượt đăng nhập 401.

Không dựng redirect_uri từ `request.base_url` hay header `Host` — đó là đường Host header
injection.

Dùng chung một `client_id` Google cho cả hai luồng là an toàn **vì** gate tách theo luồng:
web redirect_uri không bao giờ tới được nhánh POST, và ngược lại. Google Cloud Console đăng
ký thêm đúng một Authorized redirect URI:
`https://<domain>/api/auth/google/callback`.

**Preview deployment của Vercel sinh domain ngẫu nhiên** nên không đăng ký được. Đăng nhập
web chỉ chạy trên production domain. Trên preview sẽ luôn thấy `redirect_uri_mismatch` và
nó trông y như lỗi code.

### 3.7 Logout — có hai chỗ đọc token, không phải một

`bearer_token` được dùng ở **hai** nơi:

- `deps.py:36` — mọi endpoint, qua `optional_user_id`
- `router.py:42` — riêng logout

Chỉ sửa chỗ đầu thì logout của web trả 204 mà **không thu hồi gì**: `service.logout` nhận
`None` rồi return im lặng (`service.py:131-133`). Người dùng bấm đăng xuất, thấy màn đăng
nhập, nhưng phiên vẫn sống 60 ngày trên server.

Thêm dependency `session_token` đọc header trước rồi tới cookie (kèm kiểm header
`X-IELTS-Web`), dùng ở **cả hai** chỗ. Logout xoá cookie trong response.

### 3.8 Hạn cookie trượt theo hạn phiên

`resolve_user_id` gia hạn `expires_at` trong DB mỗi ngày dùng (`service.py:124-127`), còn
`Max-Age` của cookie đóng băng lúc phát. Người dùng vào hàng ngày vẫn bị đá ra đúng ngày thứ
60 dù phiên còn sống.

Cách sửa rẻ nhất: **`GET /api/auth/me` set lại cookie phiên**. Web gọi `/api/auth/me` mỗi lần
mở app (nó không có storage để đọc user như extension), nên cookie tự làm mới. Một chỗ, không
phải luồn `Response` qua dependency.

### 3.9 Lỗi giữa luồng điều hướng

`AppError` ném từ callback sẽ được exception handler trả JSON `{code, message, retryable}` —
một khối JSON trần giữa màn hình, cho một người đang ở giữa một lượt điều hướng trình duyệt.

Hai route web bắt `AppError` và `302 → /?authError=<CODE>`, `CODE` lấy từ tập cố định
(`UNAUTHORIZED`, `FORBIDDEN`, `AUTH_UNAVAILABLE`). SPA ánh xạ mã sang thông điệp tiếng Việt
và hiển thị trên màn đăng nhập.

**Không thêm mã lỗi mới.** `test_error_code_mapping.py:67` khoá cứng tập 9 tên, và
`shared/types.ts` phía extension là bản gương — thêm mã mới bắt phải sửa cả hai, mà phía
extension thì không có gì đỏ khi backend đẻ mã lạ.

### 3.10 Không cần migration

Đường cookie dùng lại nguyên bảng `user_session` và nguyên cơ chế hash SHA-256. Không có
bảng phiên thứ hai. Điều này cũng tránh làm đỏ `test_auth_migration.py:116`, vốn khoá cứng
tập bảng có cột `user_id` = `{vocab_entry, user_session, gemini_usage}`.

---

## 4. Phục vụ SPA — FastAPI `StaticFiles`, không rewrites

### 4.1 Vì sao không dùng rewrites của Vercel

Ba lý do độc lập, mỗi lý do đủ để loại:

1. `test_deploy_readiness.py:171` **cấm** `rewrites`/`routes` trong `vercel.json`.
2. Thêm `rewrites` top-level khi preset FastAPI đang bật làm **toàn bộ API trả 404** —
   rewrites chạy trước function và *thay* đường dẫn chứ không chỉ định tuyến.
3. Chế độ `services` (cách đúng hiện nay cho multi-service) **bị khoá sau quyền tài khoản**.

Thêm nữa, Caddy `reverse_proxy` toàn bộ đường dẫn về `api-service:8080` và docker-compose
không có service nào phục vụ static. Nếu SPA chỉ tồn tại trên đường Vercel thì đường Docker
vỡ — vi phạm ràng buộc #15.

**Kết luận: FastAPI tự phục vụ SPA.** Một cơ chế, hai đường deploy giống hệt nhau.

### 4.2 Lắp vào `app/main.py`

```
mount StaticFiles(directory=<static_dir>) tại /assets     (hash trong tên file → cache dài)
route GET /manifest.webmanifest, /sw.js, /icons/*         (không hash → cache ngắn)
catch-all GET  {full_path:path}  → index.html             ĐĂNG KÝ SAU CÙNG
```

Catch-all **không được nuốt `/api/*`**: đường dẫn bắt đầu bằng `/api/` phải rơi vào handler
404 cũ và giữ nguyên hình dạng `{code, message, retryable}`. Kiểm tường minh trong handler.

Thư mục static **vắng mặt là chuyện bình thường** — chạy backend-only, hoặc chạy test. Vắng
thì bỏ qua việc mount và ghi một dòng log, **không** ném. Ném là biến một bộ test đang xanh
thành `FileNotFoundError` ở một file trông chẳng liên quan gì.

### 4.3 Vercel

Root Directory giữ nguyên `api-service`. Bật toggle **"Include source files outside of the
Root Directory in the Build Step"** trên dashboard — bắt buộc, vì `packages/` và `apps/` nằm
ngoài `api-service/`.

`installCommand` **không đụng vào**: nó đang là bước `pip install` tự động của preset
FastAPI, và Vercel chỉ có **một** `installCommand` cho một project. Đặt nó thành `npm ci` là
xoá mất bước cài Python.

`npm ci` đi vào trong `buildCommand`:

```
buildCommand: "bash scripts/build-web-and-migrate.sh"
```

Script làm ba việc, theo thứ tự: `npm ci` ở gốc repo → `npm -w apps/web run build` → copy
`apps/web/dist` vào `api-service/static/` → chạy `migrate-on-deploy.sh` như cũ.

Bundling của runtime Python gói tất cả file reachable **sau** buildCommand, nên `static/` đi
theo. Đây là điểm phải kiểm bằng một lần deploy thật, không suy luận được từ code.

`migrate-on-deploy.sh` giữ nguyên, kể cả việc nó chỉ chạy khi `VERCEL_ENV == production`.

### 4.4 Docker

`Dockerfile` thêm một stage Node dựng SPA rồi copy `dist` vào `static/` của image cuối.
Caddyfile và docker-compose **không đổi** — chúng vốn đã đưa mọi đường dẫn về app.

---

## 5. PWA

### 5.1 `manifest.webmanifest`

`display: standalone`, `start_url: /`, `scope: /`, icon lấy từ `scripts/make-icons.mjs`
đang có (cần thêm cỡ 192 và 512 — hiện chỉ tới 128).

Share Target:

```json
"share_target": {
  "action": "/share",
  "method": "GET",
  "params": { "text": "text", "title": "title", "url": "url" }
}
```

`GET` chứ không `POST`: POST share target bắt buộc phải có service worker chặn request và
không dùng được khi SW chưa active, còn mình chỉ cần text. Route `/share` đọc query rồi
`replaceState` sang `/` với text đã điền vào tab Dịch — để text không nằm lại trong lịch sử
trình duyệt.

Chỉ Android. iOS bỏ qua `share_target` một cách im lặng.

### 5.2 Service worker

Viết tay, không thêm dependency (Workbox là một dependency mới).

| Loại | Chiến lược |
|---|---|
| App shell (`/`, `index.html`, `/assets/*`) | precache lúc install, cache-first |
| `GET /api/vocab`, `GET /api/stats` | stale-while-revalidate |
| Mọi `/api/*` còn lại | network-only |

Network-only cho phần còn lại là cố ý: dịch, ôn, quiz đều đổi trạng thái hoặc tốn quota
Gemini; phục vụ chúng từ cache là nói dối người dùng.

Cache của `/api/*` phải **xoá sạch khi đăng xuất** — cache dùng chung theo origin, không
theo user. Bỏ bước này là trên máy dùng chung, người sau mở app thấy sổ từ của người trước.

Tên cache mang version, bump khi đổi shell; `activate` xoá cache cũ.

### 5.3 Layout mobile

`styles.css` hiện đã fluid (`width: 100%`, flex, đã có `@media (hover: none)`). Việc còn lại:

- `.app { height: 100vh }` → `100dvh`. `100vh` trên iOS Safari tính cả thanh địa chỉ nên đáy
  màn hình bị cắt.
- `padding-bottom: env(safe-area-inset-bottom)` cho thanh tab.
- `max-width` cho màn rộng — một cột 400px kéo dài hết màn desktop trông hỏng.

---

## 6. Cấu hình mới

Mỗi biến phải có mặt ở **bốn** chỗ, nếu không `test_config_shared_env.py:144` đỏ (nó assert
bằng nhau tuyệt đối, không phải tập con):

`app/config.py` · `.env.example` · khối `environment:` của `docker-compose.yml` · bảng "Biến
môi trường" trong `README.md` (bảng **backend** 3 cột, không phải bảng VITE_).

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `WEB_BASE_URL` | `http://127.0.0.1:8080` | Origin công khai của web. Dựng `web_redirect_uri()`. Rỗng = fail closed. |
| `AUTH_GOOGLE_AUTH_URL` | `https://accounts.google.com/o/oauth2/v2/auth` | Authorization endpoint. `auth_google_token_url` **không** tái dùng được — nó là base_url của httpx client và code POST vào path `/token`. |
| `AUTH_COOKIE_SECURE` | `auto` | `auto`\|`true`\|`false`. Kiểu `str`, không `bool \| None`. |
| `WEB_STATIC_DIR` | `static` | Tương đối so với `api-service/`. Vắng thì không mount. |

Bỏ quên khối `environment:` của docker-compose là bẫy im lặng hoàn toàn: biến đặt trong
`.env` không tới được container, test và chạy local đều xanh. Chính comment ở
`docker-compose.yml:47-48` đang cảnh báo đúng ca này cho các biến `AUTH_*`.

---

## 7. Test

### 7.1 Backend

Bẫy phải né: `TestClient` là `httpx.Client` nên **giữ cookie jar** suốt vòng đời
`with TestClient(...)`. Với Bearer thì vô hại; với cookie nó làm test "chưa đăng nhập" xanh
giả sau khi một test khác trong cùng client đã đăng nhập. Mọi test đường cookie phải dùng
client riêng hoặc `client.cookies.clear()` tường minh.

Phải viết mới:

- `test_auth_cookie.py` — đọc token từ cookie; header thắng khi có cả hai; **thiếu
  `X-IELTS-Web` thì 401**; cookie + header đủ thì 200.
- `test_auth_web_flow.py` — `start` set state và redirect đúng; callback thiếu state → 401;
  state rỗng cả hai bên → 401 (không phải 200); state non-ASCII → 401 chứ không 500; callback
  thành công set cookie `__Host-` với đủ thuộc tính; lỗi → redirect `/?authError=`.
- `test_auth_redirect_uri_tach_hai_luong.py` — redirect_uri của web gửi vào `POST
  /api/auth/google` phải 401, và **không chạm Google** (soi theo
  `test_auth_router.py:151-159` đang có).
- `test_spa_static.py` — `/api/khong-ton-tai` vẫn trả JSON `NOT_FOUND`; đường khác trả
  `index.html`; thiếu thư mục static thì app vẫn khởi động được.
- `test_multi_user_isolation.py` — 14 test hiện viết tay từng cái theo đường Bearer. Cookie
  là **đường xác thực thứ hai cho mọi endpoint chạm dữ liệu học**, nên phải chứng minh nó cô
  lập y hệt. Thêm một lớp parametrize theo cơ chế xác thực thay vì nhân đôi 14 test.

  *Đã làm:* `NguoiDungTest.headers` nhận thêm trường `che_do`, và fixture `hai_nguoi` được
  parametrize `["bearer", "cookie"]`. Cookie gửi bằng header `Cookie` thô nên nó vẫn chỉ là
  một dict header — **không một dòng nào trong 14 test phải sửa**, mà số test thành 28.

**Bẫy đã vấp và cách xử lý:** `TestClient` mặc định `http://testserver`, mà httpx KHÔNG gửi
lại cookie `Secure` qua http. Triệu chứng là mọi test đường cookie hỏng với "state không
khớp" — một thông điệp trỏ đi hoàn toàn sai hướng. Fixture `client` nay dùng
`base_url="https://testserver"`, đúng với production (Caddy terminate TLS, Vercel mặc định).

Sẽ đỏ và phải cập nhật:

- `test_config_shared_env.py` — 4 biến mới.
- `test_deploy_readiness.py` — `buildCommand` đổi tên script.

### 7.2 Extension

`npm test` + `npm run build` phải xanh **không đổi một dòng test nào** sau khi rút ruột.
Test nào phải sửa nội dung (không phải sửa đường import) là dấu hiệu đã đổi hành vi — dừng
lại và xem lại.

### 7.3 Web

- Adapter: `SettingsStore` trên `localStorage`, `LastResultStore` trên `sessionStorage`.
- `sendToBackground` phiên bản web trả đúng hình dạng `{ ok, error }` khi `operations` ném.
- Service worker: chiến lược cache đúng theo bảng; xoá cache khi đăng xuất.
- Route `/share` đọc query và điền vào tab Dịch.

Test đặt cạnh file được test, query theo vai trò/nhãn người dùng thấy (RTL) — như quy ước
đang có.

---

## 8. Việc phát hiện được nhưng KHÔNG làm trong phase này

Ghi lại để không mất:

1. **`api/index.py` là code chết trên đường Vercel.** Preset FastAPI dò
   `app.py|index.py|server.py|main.py|wsgi.py|asgi.py` ở root hoặc trong `src/`/`app/` —
   `api/` không nằm trong danh sách. Entrypoint thật là `app/main.py:155`. Toàn bộ
   `RestoreOriginalPath` không bao giờ chạy, và `test_vercel_entry.py` đang test một đường
   không tồn tại. Nó vẫn đúng cho đường Docker nên không gây hại, nhưng docstring của nó mô
   tả một cấu hình `vercel.json` đã bị xoá ở commit `097f8e4`.

2. **CLAUDE.md ràng buộc #15 mô tả sai thực tế.** Nó nói `vercel.json` rewrite mọi đường dẫn
   và `includeFiles` là bắt buộc. Cả hai đã bị xoá; `prompts/*.md` vẫn tới nơi vì runtime
   Python của Vercel gói tất cả file reachable, không tree-shaking. Cần sửa lại tài liệu.

3. **`maxDuration: 60` đã biến mất** khỏi `vercel.json` cùng commit đó, trong khi `DEPLOY.md`
   vẫn hướng dẫn đặt `GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS` dựa trên giả định nó còn đó.

4. **`GET /api/srs/due` gọi Gemini ngoài quota guard.** Header bắt buộc ở mục 3.4 chặn được
   đường CSRF, nhưng bản thân việc một endpoint GET tiêu quota mà không qua guard vẫn là một
   vấn đề riêng.

5. **`resolve_user_id` trả `None` cho mọi ca hỏng** — token rác, hết hạn, đã thu hồi không
   phân biệt được. Web không có cách nào biết nên tự làm mới phiên hay bắt đăng nhập lại.
