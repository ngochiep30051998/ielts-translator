# IELTS Translator

Chrome extension dịch hai chiều Việt-Anh chuẩn IELTS band 6.5+, kèm sổ từ vựng.
Chạy hoàn toàn trên máy cá nhân: extension gọi Spring Boot ở `127.0.0.1:8080`,
backend gọi Gemini.

## Chạy lần đầu

1. Lấy Gemini API key tại https://aistudio.google.com/apikey

2. Tạo file `.env` ở thư mục gốc:
   ```bash
   cp .env.example .env
   ```
   Điền `GEMINI_API_KEY`. Để trống `EXTENSION_ID` ở bước này.

3. Build extension:
   ```bash
   cd extension && npm install && npm run build
   ```

4. Load vào Chrome: mở `chrome://extensions`, bật Developer mode,
   bấm "Load unpacked", chọn thư mục `extension/dist`.

5. Copy extension ID Chrome hiển thị, dán vào `EXTENSION_ID` trong `.env`.
   ID này cố định giữa các lần build nhờ field `key` trong manifest.

6. Khởi động backend:
   ```bash
   docker compose up -d --build
   ```

7. Mở trang Options của extension, bấm "Kiểm tra kết nối".
   Phải thấy "Backend đang chạy, Gemini đã cấu hình."

## Dùng hàng ngày

```bash
docker compose up -d      # bật backend
docker compose down       # tắt backend, dữ liệu từ vựng vẫn còn
```

Bôi đen text bất kỳ trên web để dịch. Bấm `+` để lưu vào sổ, `⤢` để mở side panel.

## Chạy backend từ IntelliJ (không qua Docker)

Chỉ bật Postgres bằng Docker, app chạy thẳng từ IDE:

```bash
docker compose up -d db      # KHÔNG bật service app, nó chiếm cổng 8080
```

Không cần khai báo gì thêm: `backend/config/application-local.yml` đã có trong repo.

Cần hiểu đúng cơ chế: **`application.yml` không đọc `.env`** — nó chỉ đọc *biến môi
trường*. Trong container, `docker compose` mới là thứ parse `.env` rồi bơm thành
biến môi trường. Chạy từ IDE không có ai làm bước đó, nên profile `local` phải tự
nạp `.env` vào Environment:

```yaml
spring:
  config:
    import: "optional:file:../.env[.properties]"
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:ielts}
    ...
gemini:
  api-key: ${GEMINI_API_KEY:}
  ...
```

`.env` là `KEY=value` nên đọc được như `.properties`; hậu tố `[.properties]` báo
cho Spring biết định dạng vì tên file không có đuôi quen thuộc. Đường dẫn tính
theo working directory của run config (`backend/`), nên `../.env` là file ở gốc.
Placeholder được resolve lúc *đọc* property chứ không phải lúc parse file, nên
khai `import` cùng document vẫn kịp cho các mục bên dưới.

File này không chứa giá trị thật nào — toàn `${VAR}` trỏ về `.env` — nên commit
được và `.env` vẫn là nguồn sự thật duy nhất.

Đặt ở `backend/config/` chứ **không** phải `src/main/resources/`: `Dockerfile` có
`COPY src ./src`, mọi file trong `src/` đều bị đóng vào image và jar. Spring Boot
đọc `file:./config/` theo mặc định nên đặt ở đây vẫn chạy mà không rò gì ra image.

Rồi Run configuration **Backend local** (đã có sẵn trong `.run/`): main class
`com.hiepnn.ieltstranslator.IeltsTranslatorApplication`, working directory `backend`,
env `SPRING_PROFILES_ACTIVE=local`. Nếu IntelliJ báo thiếu module, chọn module Maven
của `backend/pom.xml` trong dropdown (project `.idea` ban đầu chưa import pom này —
chuột phải `backend/pom.xml` → Add as Maven Project).

Kiểm tra: `curl http://127.0.0.1:8080/api/health` phải trả `geminiConfigured: true`.

Nếu `geminiConfigured` trả `false`, gần như chắc chắn đường dẫn `../.env` không
khớp — kiểm tra working directory của run config đúng là `backend/` chưa.

## Biến môi trường

Tất cả nằm ở `.env` thư mục gốc, mẫu xem `.env.example`. `docker-compose.yml`
không hardcode thông số nào nữa:

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `GEMINI_API_KEY` | (bắt buộc) | |
| `GEMINI_MODEL` | `gemini-2.5-flash` | |
| `EXTENSION_ID` | (bắt buộc) | Thiếu thì CORS chặn extension |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `ielts` | Xem cảnh báo bên dưới |
| `DB_PORT` | `5432` | Cổng publish ra host |
| `APP_PORT` | `8080` | Cổng publish ra host |
| `DB_HOST` | `localhost` | docker compose set `db` |
| `SERVER_ADDRESS` | `127.0.0.1` | Trong container phải là `0.0.0.0` |
| `SERVER_PORT` | `8080` | Cổng backend lắng nghe |
| `GEMINI_BASE_URL` | endpoint Google | Đổi khi test bằng WireMock |
| `GEMINI_TIMEOUT_SECONDS` | `15` | |
| `GEMINI_RETRY_BACKOFF_MS` | `1000` | |

`backend/src/main/resources/application.yml` không hardcode giá trị nào nữa — mọi
mục đều là `${BIEN:mặc-định}`, và default trong file chính là cấu hình chạy local.
JDBC URL được ghép phẳng từ `DB_HOST`/`DB_PORT`/`DB_NAME`, không còn biến `DB_URL`.

Hai chỗ dễ vấp:

- **`POSTGRES_*` chỉ có tác dụng ở lần khởi tạo data directory đầu tiên.** Đổi
  `DB_NAME`/`DB_USER`/`DB_PASSWORD` khi volume `ielts_pgdata` đã tồn tại thì
  container vẫn chạy với giá trị cũ, còn app thì nối bằng giá trị mới và fail
  xác thực. Muốn đổi thật: `docker compose down -v` — lệnh này **xoá sạch sổ từ
  vựng**, export CSV trước khi chạy.
- **`DB_PORT`/`APP_PORT` chỉ đổi cổng trên host.** Trong mạng nội bộ của compose
  db luôn là 5432 và app luôn là 8080, nên `DB_URL` của service `app` giữ nguyên
  `db:5432`. Nếu đổi `APP_PORT`, nhớ sửa cả `backendUrl` trong trang Options của
  extension và `host_permissions` trong `manifest.config.ts`.

## Chạy test

```bash
cd backend && mvn test          # cần Docker cho Testcontainers
cd extension && npm test
```

## Chỉnh prompt

Prompt nằm ở `backend/src/main/resources/prompts/*.md`. Sửa xong nhớ tăng
`version:` ở đầu file — cache sẽ tự hết hiệu lực. Rồi `docker compose up -d --build`.
