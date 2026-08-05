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

Tạo `backend/config/application-local.yml` (đã gitignore), lấy giá trị từ `.env`:

```yaml
spring:
  datasource:
    url: "jdbc:postgresql://localhost:5432/ielts"   # localhost:${DB_PORT}/${DB_NAME}
    username: "ielts"                                # ${DB_USER}
    password: "ielts"                                # ${DB_PASSWORD}
gemini:
  api-key: "..."
  model: "gemini-2.5-flash"
extension:
  id: "..."          # cùng giá trị EXTENSION_ID trong .env
```

Đặt ở `backend/config/` chứ **không** phải `src/main/resources/`: `Dockerfile` có
`COPY src ./src` và repo không có `.dockerignore`, nên mọi file trong `src/` đều bị
đóng vào image và jar. Spring Boot đọc `file:./config/` theo mặc định nên đặt ở đây
vẫn chạy mà không rò key ra image.

Rồi Run configuration **Backend local** (đã có sẵn trong `.run/`): main class
`com.hiepnn.ieltstranslator.IeltsTranslatorApplication`, working directory `backend`,
env `SPRING_PROFILES_ACTIVE=local`. Nếu IntelliJ báo thiếu module, chọn module Maven
của `backend/pom.xml` trong dropdown (project `.idea` ban đầu chưa import pom này —
chuột phải `backend/pom.xml` → Add as Maven Project).

Kiểm tra: `curl http://127.0.0.1:8080/api/health` phải trả `geminiConfigured: true`.

Lưu ý: cấu hình nằm ở hai chỗ — `.env` (cho docker compose) và
`backend/config/application-local.yml` (cho IDE). Đổi key Gemini hoặc thông số
PostgreSQL thì nhớ đổi cả hai.

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
