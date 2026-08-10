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

### 1.4 Nếu muốn mang dữ liệu cũ sang

```bash
docker compose exec -T db pg_dump -U ielts --data-only --no-owner ielts > data.sql
```

Rồi `psql <chuỗi-kết-nối-5432> -f data.sql`. Dùng cổng **5432** (direct) cho việc nhập một
lần — pooler không hợp với transaction dài.

---

## 2. Vercel

### 2.1 Root Directory

**`api-service`**, không phải thư mục gốc repo. Đặt sai thì Vercel không thấy `vercel.json`
lẫn `requirements.txt`.

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
| `TZ` | `Asia/Ho_Chi_Minh` — quyết định "hôm nay" của lịch ôn |
| `GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS` | **`25`** — xem dưới |

Hai thứ **không** cần đặt: `DB_HOST`/`DB_PORT`/… (đã có `DATABASE_URL`) và `VERCEL` (nền
tảng tự gán).

`AUTH_BOOTSTRAP_EMAIL` cũng không cần — nó chỉ dùng lúc chạy migration, mà migration thì đã
áp ở bước 1.3.

### 2.3 Vì sao phải hạ timeout sinh quiz xuống 25

`vercel.json` khai `maxDuration: 60` — đó là **trần của gói Hobby**, không nâng được.

Một lượt sinh quiz xấu nhất tốn `MAX_ATTEMPTS × timeout + backoff`. Với mặc định 30s thì cận
trên là `2 × 30 + 1 = 61 giây` > 60: Vercel giết function **giữa** lượt gọi Gemini — người
dùng thấy request treo rồi đứt, quota Gemini vẫn bị trừ, log chỉ có một dòng timeout không
nói được nguyên nhân.

Trần an toàn là **29s**; `25` chừa chỗ cho phần còn lại của request. Mặc định 30 giữ nguyên
cho Docker vì ở đó không có `maxDuration`.

`tests/test_deploy_readiness.py::test_max_duration_khai_tuong_minh_va_du_cho_mot_timeout_dung_duoc`
canh quan hệ này — sửa `MAX_ATTEMPTS` hay `maxDuration` mà quên chỗ kia thì test đỏ.

### 2.4 Deploy

```bash
uv run --directory api-service --with vercel-cli vercel --prod
```

hoặc nối GitHub repo trong dashboard.

### 2.5 Kiểm

```bash
curl https://<project>.vercel.app/api/health
```

Phải trả `{"status":"UP","dbConnected":true,"geminiConfigured":true}`.

`dbConnected: false` = `DATABASE_URL` sai hoặc chưa áp schema.
`geminiConfigured: false` = quên `GEMINI_API_KEY`.

```bash
curl -i https://<project>.vercel.app/api/vocab
```

Phải là `401` với body `{"code":"UNAUTHORIZED",...}`. Nếu ra `404` hoặc HTML thì `rewrites`
chưa ăn.

---

## 3. Extension

Ràng buộc #10: **ba chỗ phải khớp**, không phải hai.

1. `extension/manifest.config.ts` → `host_permissions`: đổi
   `'https://ielts.example.com/*'` thành `'https://<project>.vercel.app/*'`
2. `extension/src/shared/settings.ts` → `backendUrl` mặc định
3. Trang Options (ô nhập tự do) — người dùng đang dùng phải tự sửa, hoặc bạn xoá key cũ

Options là ô nhập tự do **nhưng Chrome chỉ cho gọi origin đã khai trong manifest**. Trỏ sang
domain chưa khai thì request chết **im lặng**: không lỗi mạng, không lỗi CORS, không gì cả.

```bash
cd extension && npm run build
```

Rồi tải lại extension đã unpack.

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
