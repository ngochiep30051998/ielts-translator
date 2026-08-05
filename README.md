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

## Chạy test

```bash
cd backend && mvn test          # cần Docker cho Testcontainers
cd extension && npm test
```

## Chỉnh prompt

Prompt nằm ở `backend/src/main/resources/prompts/*.md`. Sửa xong nhớ tăng
`version:` ở đầu file — cache sẽ tự hết hiệu lực. Rồi `docker compose up -d --build`.
