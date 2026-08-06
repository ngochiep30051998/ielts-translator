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

## Ôn tập

Mỗi từ đơn lưu vào sổ tự động vào lịch ôn (câu dài thì không — flashcard cả câu
không có giá trị ôn tập). Số trên icon extension là số thẻ đến hạn, tự cập nhật
mỗi 30 phút và ngay sau khi bạn ôn hoặc lưu từ mới.

Mở side panel → tab **Ôn tập**. Mỗi thẻ là một câu trắc nghiệm bốn lựa chọn, trộn
ngẫu nhiên hai chiều:

- **Anh → Việt:** hiện từ, IPA và nút phát âm, bạn chọn nghĩa đúng.
- **Việt → Anh:** hiện nghĩa tiếng Việt, bạn chọn từ đúng.

Bấm phím `1`–`4` hoặc bấm chuột để chọn. Chọn xong hiện ngay đáp án đúng cùng phần
chi tiết (từ loại, CEFR, band, định nghĩa tiếng Anh); bấm **Tiếp** hoặc `Enter` sang
thẻ sau.

Khoảng cách ôn lần sau suy ra từ kết quả và thời gian bạn trả lời, không phải tự chấm:

| Kết quả | Ảnh hưởng |
|---|---|
| Sai | về 1 ngày, EF −0.32, đếm một lần quên |
| Đúng, dưới 5 giây | 1 ngày → 6 ngày → × EF, rồi × 1.3; EF +0.10 |
| Đúng, 5–15 giây | 1 ngày → 6 ngày → × EF |
| Đúng, 15–60 giây | khoảng cách × 1.2, EF −0.14 |
| Đúng, trên 60 giây | tính như 5–15 giây — quá lâu thì coi như bạn rời máy, không phạt |

Ba đáp án sai do AI sinh sẵn cho từng từ rồi lưu lại, nên mỗi từ chỉ tốn một lượt gọi
Gemini trong suốt vòng đời. Từ vừa lưu có thể chưa kịp có bộ đáp án sai riêng; lúc đó
bài ôn tạm mượn nghĩa của các từ khác trong hàng đợi, bộ thật sẽ có ở lần ôn sau.

Số từ **mới** mỗi ngày mặc định giới hạn 30, đổi trong Options. Thẻ đã đến hạn
không bị giới hạn — đến hạn bao nhiêu hiện bấy nhiêu.

## Chạy backend từ IntelliJ (không qua Docker)

Chỉ bật Postgres bằng Docker, app chạy thẳng từ IDE:

```bash
docker compose up -d db      # KHÔNG bật service app, nó chiếm cổng 8080
```

`.env` ở thư mục gốc được nạp thẳng bởi `application.yml`:

```yaml
spring:
  config:
    import:
      - "optional:file:../.env[.properties]"   # cwd = backend/
      - "optional:file:./.env[.properties]"    # cwd = thư mục gốc
```

Đặt ở `application.yml` chứ **không** phải file profile-specific: profile chỉ bật
khi dùng đúng một run config cụ thể, mà cách chạy tự nhiên nhất trong IntelliJ là
bấm mũi tên xanh cạnh hàm `main` — lúc đó IDE sinh một run config tạm không có
profile nào. Để việc nạp `.env` phụ thuộc profile là tự đặt bẫy.

Hai ứng viên đường dẫn vì working directory khác nhau tuỳ cách chạy: run config
`Backend local` và `mvn spring-boot:run` chạy trong `backend/`, còn config tạm của
IntelliJ mặc định `$PROJECT_DIR$` là thư mục gốc. `optional:` để trong container
(không có `.env`, biến đến từ compose) vẫn chạy bình thường.

`.env` là `KEY=value` nên đọc được như `.properties`; hậu tố `[.properties]` báo
cho Spring biết định dạng vì tên file không có đuôi quen thuộc.

Run configuration **Backend local** (đã có sẵn trong `.run/`): main class
`com.hiepnn.ieltstranslator.IeltsTranslatorApplication`, working directory `backend`,
env `SPRING_PROFILES_ACTIVE=local`. Nếu IntelliJ báo thiếu module, chọn module Maven
của `backend/pom.xml` trong dropdown (project `.idea` ban đầu chưa import pom này —
chuột phải `backend/pom.xml` → Add as Maven Project).

Kiểm tra: `curl http://127.0.0.1:8080/api/health` phải trả `geminiConfigured: true`.

### Khi chạy từ IntelliJ, Spring tìm `.env` ở gốc bằng cách nào

Hai thứ phụ thuộc **working directory** của run config, và cả hai đều hỏng im lặng
nếu đặt sai:

1. Tìm chính `application-local.yml` — Spring chỉ dò `file:./config/` theo mặc
   định. cwd sai thì file không được nạp, app vẫn khởi động, key rỗng.
2. Tìm `.env` — `../.env` tính từ cwd.

Run config `Backend local` xử lý cả hai:

- `WORKING_DIRECTORY = $PROJECT_DIR$/backend` → `./config/` và `../.env` đều trúng.
- `--spring.config.additional-location=file:$PROJECT_DIR$/backend/config/` → đường
  dẫn **tuyệt đối**, nên dù ai đó đổi working directory thì vẫn tìm thấy file config.
- Trong `application-local.yml`, `spring.config.import` khai hai ứng viên
  (`../.env` và `./.env`) nên `.env` ở gốc vẫn được nạp khi cwd là thư mục gốc —
  đúng cái IntelliJ mặc định (`$PROJECT_DIR$`) khi bạn tự bấm mũi tên xanh cạnh
  hàm `main` thay vì dùng run config có sẵn.

Nếu `geminiConfigured` vẫn trả `false`, bật log để xem Spring nạp những file nào:

```
-Dlogging.level.org.springframework.boot.context.config=TRACE
```

(dán vào ô VM options của run config). Log sẽ liệt kê từng config data location
đã thử và cái nào tồn tại.

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
| `TZ` | `Asia/Ho_Chi_Minh` | Quyết định "hôm nay" của lịch ôn. Container mặc định UTC → thiếu biến này thì ngày ôn đổi lúc 07:00 thay vì nửa đêm |

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
