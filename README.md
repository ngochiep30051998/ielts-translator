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

Tạo `backend/config/application-local.yml` (đã gitignore) chứa key của bạn:

```yaml
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

Lưu ý: key nằm ở hai chỗ — `.env` (cho docker compose) và
`backend/config/application-local.yml` (cho IDE). Đổi key nhớ đổi cả hai.

## Chạy test

```bash
cd backend && mvn test          # cần Docker cho Testcontainers
cd extension && npm test
```

## Chỉnh prompt

Prompt nằm ở `backend/src/main/resources/prompts/*.md`. Sửa xong nhớ tăng
`version:` ở đầu file — cache sẽ tự hết hiệu lực. Rồi `docker compose up -d --build`.
