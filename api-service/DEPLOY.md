# Deploy api-service lên Vercel + Supabase

Thứ tự bắt buộc: **Supabase trước** (có schema và chuỗi kết nối), **Vercel sau**, **extension
cuối** (cần biết domain thật).

Mọi bước dưới đây tôi chưa chạy được — không có tài khoản của bạn. Phần đã kiểm chứng là
code: `tests/test_deploy_readiness.py` canh những chỗ chỉ hỏng sau khi deploy, và khối SQL ở
bước 1.3 đã được áp thử lên một Postgres 16 trắng.

---

## 1. Supabase

### 1.1 Tạo project

Chọn region **Singapore** — `vercel.json` ghim `regions: ["sin1"]`, và mỗi truy vấn đi vòng
qua nửa vòng trái đất là cộng thẳng vào thời gian phản hồi của từng lượt tra từ.

### 1.2 Lấy chuỗi kết nối

Settings → Database → Connection string → **Transaction pooler** (cổng `6543`).

Đừng lấy Direct connection (`5432`): serverless mở kết nối mới mỗi lượt gọi, và hạn mức kết
nối trực tiếp của Supabase sẽ hết trong vài phút có tải.

```
postgresql://postgres.<ref>:<mật-khẩu>@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

`api-service` tự nhận ra cổng `6543` và **tắt prepared statement**. Đây không phải tinh
chỉnh cho vui: psycopg tự tạo prepared statement sau 5 lần chạy cùng một câu, còn transaction
pooler thì ghép nhiều client lên chung một backend — câu thứ sáu rơi vào backend chưa từng
thấy statement đó và chết bằng `prepared statement "_pg3_N" does not exist`, **rời rạc, chỉ
dưới tải**. Xem `app/db.py`.

### 1.3 Áp schema

Migration **không** chạy lúc cold start (nhiều instance cùng `ALTER TABLE` là công thức để
khoá lẫn nhau), nên phải áp một lần bằng tay:

```bash
uv run python -m app.migrator | pbcopy
```

Dán vào SQL Editor của Supabase rồi chạy. Lệnh trên gộp cả 7 migration, thay
`${bootstrap_email}` bằng `AUTH_BOOTSTRAP_EMAIL` trong `.env`, và ghi sẵn `api_schema_history`
để lần khởi động sau không chạy lại.

In ra màn hình chứ không ghi file có chủ ý: file SQL đã nhúng sẵn email là thứ sẽ bị commit
nhầm.

Kiểm lại trong SQL Editor:

```sql
select tablename from pg_tables where schemaname = 'public' order by 1;
select email from app_user;
```

Phải thấy 11 bảng và đúng một tài khoản gốc mang email bootstrap của bạn.

### 1.4 Ba chuỗi kết nối, dùng đúng chỗ

Supabase đưa ba lựa chọn và chúng KHÔNG thay thế được cho nhau:

| Loại | Host / cổng | Dùng cho | Bẫy |
|---|---|---|---|
| **Direct connection** | `db.<ref>.supabase.co:5432` | (tránh) | **Chỉ IPv6.** Mạng không có IPv6 sẽ chết bằng `Network is unreachable` ngay ở bước nối |
| **Session pooler** | `aws-0-<region>.pooler.supabase.com:5432` | migration, `pg_dump`/`psql` | user phải là `postgres.<ref>`, không phải `postgres` |
| **Transaction pooler** | `aws-0-<region>.pooler.supabase.com:6543` | `DATABASE_URL` trên Vercel | không hợp cho DDL |

Dùng **Session pooler** cho mọi thao tác từ máy bạn. Direct connection chỉ hơn ở chỗ không
qua pooler, mà cái giá là cả một lớp lỗi mạng không liên quan gì tới dự án.

Mật khẩu có ký tự đặc biệt (`@ : / ? # &`) thì phải URL-encode, không thì phần host bị cắt
sai và thông điệp lỗi sẽ nói về một host không tồn tại.

### 1.5 Nếu muốn mang dữ liệu cũ sang

```bash
docker compose exec -T db pg_dump -U ielts --data-only --no-owner --exclude-table=flyway_schema_history ielts > /tmp/data.sql
```

Rồi `psql "<chuỗi-session-pooler-5432>" -f /tmp/data.sql`.

`app_user` đã có một dòng do V6 tạo nên bản dump sẽ đụng khoá trùng email. Chỉ khi CHƯA ai
đăng nhập vào Supabase mới được dọn nó trước: `delete from app_user;` — sau đó thì bảng này
đã có phiên và dữ liệu thật.

---

## 2. Vercel

### 2.1 Root Directory

**`api-service`**, không phải thư mục gốc repo. Đặt sai thì Vercel không thấy `vercel.json`
lẫn `requirements.txt`.

### 2.1b Bật "Include source files outside of the Root Directory" — BẮT BUỘC

Settings → Build and Deployment → bật **"Include source files outside of the Root Directory
in the Build Step"**.

Root Directory là `api-service`, nhưng web app nằm ở `apps/web` và dùng chung
`packages/core` — cả hai ở NGOÀI thư mục đó. Không bật thì Vercel chỉ tải lên `api-service/`
và bước build không tìm thấy monorepo.

`scripts/build-web-and-migrate.sh` kiểm tường minh và **dừng hẳn** nếu thiếu, kèm thông điệp
chỉ đúng vào ô này. Bỏ qua rồi deploy tiếp là kiểu hỏng tệ nhất: build xanh, API chạy, chỉ có
web là 404 — và không dòng log nào nói vì sao.

### 2.1c Web app được phục vụ thế nào

`buildCommand` là `bash scripts/build-web-and-migrate.sh`, làm hai việc theo thứ tự: dựng
SPA vào `api-service/static/`, rồi chạy migration như cũ.

Lúc chạy, **FastAPI tự phục vụ SPA** (`app/web_static.py`): `/` và mọi đường dẫn lạ trả
`index.html`, `/assets/*` trả file tĩnh, còn `/api/*` vẫn đi vào router như thường.

**KHÔNG dùng `rewrites` của Vercel** — có ba lý do độc lập, mỗi lý do đủ để loại:

1. `test_deploy_readiness.py::test_vercel_json_khong_duoc_co_rewrites` cấm.
2. Thêm `rewrites` khi preset FastAPI đang bật làm **toàn bộ API trả 404** (rewrite chạy
   trước function và *thay* đường dẫn chứ không chỉ định tuyến).
3. Chế độ `services` bị khoá sau quyền tài khoản.

Và lý do quan trọng hơn cả ba: đường Docker phải khớp (ràng buộc #15). `Caddyfile`
reverse_proxy toàn bộ đường dẫn về `api-service:8080`, nên nếu SPA chỉ tồn tại nhờ cấu hình
riêng của Vercel thì bản tự dựng vỡ. `Dockerfile` có một stage Node làm đúng việc mà script
trên làm.

`installCommand` **không đụng vào** — nó đang là bước `pip install` tự động của preset
FastAPI, và Vercel chỉ có MỘT `installCommand`. `npm ci` nằm trong `buildCommand`.

### 2.2 Biến môi trường

Đặt trong Project Settings → Environment Variables:

| Biến | Giá trị |
|---|---|
| `DATABASE_URL` | chuỗi kết nối transaction pooler ở bước 1.2 |
| `GEMINI_API_KEY` | như `.env` |
| `GEMINI_MODEL` | như `.env` |
| `EXTENSION_ID` | như `.env` — thiếu thì CORS chặn extension |
| `AUTH_GOOGLE_CLIENT_ID` | như `.env` |
| `AUTH_GOOGLE_CLIENT_SECRET` | như `.env` — **chỉ ở đây, không bao giờ vào bundle extension** |
| `AUTH_ALLOWED_EMAILS` | như `.env` — **rỗng = khoá hết**, cố ý |
| `AUTH_SESSION_DAYS` | `60` |
| `AUTH_DAILY_GEMINI_CALLS` | `300` |
| `APP_TZ` | `Asia/Ho_Chi_Minh` — quyết định "hôm nay" của lịch ôn. **`APP_TZ` chứ không phải `TZ`**, xem dưới |
| `GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS` | **`25`** — xem dưới |
| `WEB_BASE_URL` | **`https://<domain-production>`** — không có dấu `/` ở cuối. Backend dựng redirect URI đăng nhập web từ đây. Thiếu thì `/api/auth/google/start` trả `AUTH_UNAVAILABLE` |

`AUTH_COOKIE_SECURE` không cần đặt: mặc định `auto` tự bật `Secure` vì `WEB_BASE_URL` là
https.

**`MIGRATION_DATABASE_URL` và `AUTH_BOOTSTRAP_EMAIL` phải có ở môi trường Build**, không chỉ
Runtime — `buildCommand` chạy migration ở build time.

Hai thứ **không** cần đặt: `DB_HOST`/`DB_PORT`/… (đã có `DATABASE_URL`) và `VERCEL` (nền
tảng tự gán).

`AUTH_BOOTSTRAP_EMAIL` cũng không cần — nó chỉ dùng lúc chạy migration, mà migration thì đã
áp ở bước 1.3.

### 2.2b Đăng ký redirect URI của web trong Google Cloud Console

Thêm **một** Authorized redirect URI nữa, cạnh cái của extension:

```
https://<domain-production>/api/auth/google/callback
```

Dùng chung `client_id` với extension là an toàn, vì gate `redirect_uri` tách theo từng luồng:
`POST /api/auth/google` chỉ chấp nhận URI của extension, còn callback web dựng URI từ
`WEB_BASE_URL` phía server và không bao giờ nhận từ client.

**Preview deployment không đăng nhập web được.** Vercel sinh domain ngẫu nhiên mỗi lần deploy
nên không đăng ký trước được — trên preview sẽ luôn thấy `redirect_uri_mismatch`, và nó
trông y hệt lỗi code. Đăng nhập web chỉ chạy trên domain production cố định.

### 2.3 Vì sao là `APP_TZ` chứ không phải `TZ`

Thử đặt `TZ` trên dashboard sẽ bị từ chối: *"The name of your Environment Variable is
reserved"* — kể cả khi project chưa có biến nào tên đó. `TZ` là biến chuẩn POSIX nên nền tảng
giữ lại cho mình: AWS Lambda bên dưới **tự đặt** `TZ=:UTC`, dạng POSIX có dấu hai chấm đầu chứ
không phải key IANA.

Hậu quả nếu backend đọc thẳng biến đó: `ZoneInfo(":UTC")` ném `ZoneInfoNotFoundError` và
`GET /api/stats` trả 500, trong khi mọi endpoint khác vẫn chạy — nên triệu chứng trông giống
lỗi của riêng tính năng thống kê chứ không giống lỗi cấu hình.

Vì vậy `config.py` nhận **hai** tên cho cùng một mục, ưu tiên `APP_TZ` (`AliasChoices`), và bỏ
qua mọi giá trị bắt đầu bằng `:` để quay về mặc định `Asia/Ho_Chi_Minh`. Không đặt `APP_TZ`
thì vẫn chạy đúng giờ VN — chỉ mất khả năng đổi múi giờ. Đường Docker không đổi gì: compose
vẫn truyền `TZ`.

Gói `tzdata` nằm trong `requirements.txt` vì cùng một sự cố: `zoneinfo` đọc file hệ thống ở
/usr/share/zoneinfo và image serverless không đảm bảo có sẵn.

### 2.4 Vì sao phải hạ timeout sinh quiz xuống 25

`vercel.json` khai `maxDuration: 60` — đó là **trần của gói Hobby**, không nâng được.

Một lượt sinh quiz xấu nhất tốn `MAX_ATTEMPTS × timeout + backoff`. Với mặc định 30s thì cận
trên là `2 × 30 + 1 = 61 giây` > 60: Vercel giết function **giữa** lượt gọi Gemini — người
dùng thấy request treo rồi đứt, quota Gemini vẫn bị trừ, log chỉ có một dòng timeout không
nói được nguyên nhân.

Trần an toàn là **29s**; `25` chừa chỗ cho phần còn lại của request. Mặc định 30 giữ nguyên
cho Docker vì ở đó không có `maxDuration`.

`tests/test_deploy_readiness.py::test_max_duration_khai_tuong_minh_va_du_cho_mot_timeout_dung_duoc`
canh quan hệ này — sửa `MAX_ATTEMPTS` hay `maxDuration` mà quên chỗ kia thì test đỏ.

### 2.5 Deploy

```bash
uv run --directory api-service --with vercel-cli vercel --prod
```

hoặc nối GitHub repo trong dashboard.

### 2.6 Kiểm

```bash
curl https://<project>.vercel.app/api/health
```

Phải trả `{"status":"UP","dbConnected":true,"geminiConfigured":true}`.

`dbConnected: false` = `DATABASE_URL` sai hoặc chưa áp schema.
`geminiConfigured: false` = quên `GEMINI_API_KEY`.

```bash
curl -i https://<project>.vercel.app/api/vocab
```

Phải là `401` với body `{"code":"UNAUTHORIZED",...}`.

**Nếu ra HTML thì catch-all của SPA đang nuốt `/api/*`** — lỗi nặng, vì client sẽ cố parse
JSON, thất bại, rồi báo "backend trả phản hồi không đọc được" thay vì "cần đăng nhập".
`tests/test_spa_static.py::test_API_KHONG_bi_catch_all_nuot` canh đúng chỗ này.

Rồi kiểm web app:

```bash
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' https://<project>.vercel.app/
```

Phải là `200 text/html`. Ra `404 application/json` nghĩa là `static/index.html` không có
trong bundle — gần như luôn là do quên bật toggle ở mục 2.1b.

```bash
curl -sI https://<project>.vercel.app/api/auth/google/start | grep -i location
```

Phải redirect sang `accounts.google.com` kèm `redirect_uri` đúng domain production. Nếu thấy
`redirect_uri=https://127.0.0.1:8080/...` thì quên đặt `WEB_BASE_URL`.

Cuối cùng là PWA:

```bash
for p in /manifest.webmanifest /sw.js /icons/192.png /icons/512.png; do curl -s -o /dev/null -w "$p %{http_code} %{content_type}\n" https://<project>.vercel.app$p; done
```

Cả bốn phải `200`, và `manifest.webmanifest` phải là `application/manifest+json` — sai MIME
thì Chrome bỏ qua manifest và không hiện lời mời "Thêm vào màn hình chính".

**Kiểm trên điện thoại Android thật** (không kiểm bằng máy tính được):

1. Mở domain production trong Chrome → menu → "Thêm vào Màn hình chính". Mở app từ icon:
   phải chạy toàn màn hình, không có thanh địa chỉ.
2. Bôi đen một đoạn text ở app bất kỳ → Share → chọn IELTS Translator. App phải mở thẳng tab
   Dịch với text đã điền sẵn, và **thanh địa chỉ phải là `/`** chứ không còn `/share?text=…`.
3. Bật chế độ máy bay rồi mở lại app: phải mở được và xem lại được Sổ từ đã tải. Tab Dịch
   báo lỗi mạng là ĐÚNG — offline cố ý chỉ-đọc.

**iOS**: cài được vào màn hình chính, nhưng Safari bỏ qua `share_target` — không có mục trong
menu Share. Đó là giới hạn của nền tảng, không phải lỗi cấu hình.

---

## 3. Extension

Ràng buộc #10 từng bắt khớp tay ba chỗ. Nay `host_permissions` và `backendUrl` mặc định
cùng sinh từ **một biến**, nên chỉ còn một dòng phải sửa.

Thêm vào `extension/.env.prod` (tạo file nếu chưa có — nó bị `.gitignore` chặn):

```
VITE_BACKEND_URL=https://<project>.vercel.app
```

Rồi build bản production:

```bash
cd extension && npm run build:prod
```

`npm run build` (không hậu tố) nạp `.env.dev` và cho ra bundle trỏ `127.0.0.1:8080` — dùng
để thử trên máy, **không** phải bản đem phát hành.

Tải lại extension đã unpack. Xong.

Kiểm nếu muốn chắc — hai giá trị phải khớp:

```bash
cd extension && node -e "console.log(require('./dist/manifest.json').host_permissions)" && grep -rho 'https://[a-z0-9.-]*vercel\.app' dist/assets/*.js | sort -u
```

**Đổi `VITE_BACKEND_URL` thì BẮT BUỘC build lại.** `host_permissions` nằm trong manifest,
không phải thứ sửa được từ trang Options — và Chrome chỉ cho gọi origin đã khai ở đó. Trỏ
Options sang một domain chưa khai thì request chết **im lặng**: không lỗi mạng, không lỗi
CORS, `fetch` đơn giản là không bao giờ đi.

Danh sách luôn giữ cả `http://127.0.0.1:8080/*`, nên vẫn đổi Options về backend chạy local
để đối chiếu với bản deploy mà không phải build lại.

`manifest.config.test.ts` canh bất biến này: nó dựng manifest qua `loadEnv` (đường Node) và
đọc `DEFAULT_SETTINGS` qua `import.meta.env` (đường bundle), rồi khẳng định hai đường ra
cùng một origin.

Redirect URI của Google **không đổi** — nó dựng từ `EXTENSION_ID`
(`https://<id>.chromiumapp.org/`), không dính gì tới domain backend.

---

## 4. Ba chỗ hành vi khác Docker, biết trước thì đỡ mất thời gian

**Sinh mồi nhử chạy nền.** `BackgroundTasks` chạy sau khi response đã gửi nhưng vẫn **trong**
lượt gọi function — nên Vercel tính tiền cả quãng đó, và một lượt gọi Gemini 15 giây làm
function sống thêm 15 giây sau khi người dùng đã nhận kết quả. Chấp nhận được vì đường lười
`request_missing` sẽ bù ở lần mở tab ôn sau; nếu hoá đơn khó chịu thì chuyển sang Vercel Cron.

**Chặn trùng lặp chỉ trong một tiến trình.** `_in_flight` ở `app/srs/distractors.py` là một
`set` trong bộ nhớ. Hai instance serverless chạy song song vẫn có thể cùng sinh mồi nhử cho
một từ — chi phí là một lượt gọi Gemini thừa, không phải dữ liệu sai, vì ghi đè theo
`vocab_entry_id` là idempotent.

**`api_schema_history` không tự cập nhật.** Thêm `V8__*.sql` về sau thì phải chạy lại bước
1.3. Quên là api-service chạy trên schema cũ và lỗi sẽ hiện ra ở một endpoint ngẫu nhiên,
không phải lúc khởi động.
