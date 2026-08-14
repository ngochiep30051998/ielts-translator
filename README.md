# IELTS Translator

Chrome extension dịch hai chiều Việt-Anh chuẩn IELTS band 6.5+, kèm sổ từ vựng.
Chạy hoàn toàn trên máy cá nhân: extension gọi FastAPI ở `127.0.0.1:8080`,
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

Không có sẵn text trên trang thì mở side panel và gõ/dán thẳng vào ô trên tab **Dịch**
(`Ctrl/Cmd+Enter` để dịch). Ô này được điền sẵn đoạn của lần dịch gần nhất, nên bôi
hụt một chút thì sửa lại rồi dịch lại, không phải gõ từ đầu.

Panel đang mở không tự cập nhật khi bạn bôi đen và dịch trên trang — đóng rồi mở lại
panel để kéo kết quả mới nhất vào tab Dịch.

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

## Giao diện sáng/tối

Options có ba lựa chọn: **Theo hệ thống** (mặc định), **Sáng**, **Tối**. Chọn là đổi ngay,
không phải bấm Lưu, và áp cho cả side panel, trang Options lẫn bubble dịch trên trang web.

Lựa chọn được lưu trong `chrome.storage.local`; `shared/theme.ts` phân giải nó ra
`light`/`dark` rồi gắn `<html data-theme="…">`. **CSS không tự hỏi `prefers-color-scheme`
nữa** — nhờ vậy bộ token tối chỉ tồn tại ở đúng một chỗ (`:root[data-theme="dark"]` trong
`sidepanel/styles.css`). Bubble là ngoại lệ về cách áp: nó sống trong Shadow DOM trên
trang của người khác nên nhận chế độ qua `setBubbleTheme` và tự đặt lên host của mình,
không được đụng vào `<html>` của trang đó.

## Quiz

Mở side panel → tab **Quiz**. Chọn **số câu** (mặc định 10) và tick loại muốn làm,
rồi bấm **Tạo đề**:

| Loại | Đề bài | Cách chấm |
|---|---|---|
| **Điền từ** | Một câu có chỗ trống `___` kèm gợi ý nghĩa | So chuỗi, bỏ phân biệt hoa thường — **không** tự chia lại dạng từ (`mitigated` không tính là `mitigate`) |
| **Chọn cụm từ** | Bốn lựa chọn, một đúng | So lựa chọn |
| **Tự viết câu** | Viết một câu tiếng Anh dùng từ đó | AI chấm nghĩa + ngữ pháp, kèm nhận xét và bản viết lại |

Chỉ **Tự viết câu** tốn token khi chấm; hai loại kia backend tự so, không gọi AI.

Chỉ những từ **đã ôn ít nhất một lượt** mới vào quiz. Sổ chưa có từ nào như vậy thì
tab hiện *"Chưa có từ nào đủ điều kiện"* — đó là đúng, không phải lỗi. Từ ít làm
nhất được ưu tiên, rồi tới từ hay quên nhất.

Đề sinh xong được lưu lại, nên mở quiz lần sau không gọi lại AI cho những câu bạn
chưa làm. Sửa prompt quiz và tăng `version:` sẽ làm đề cũ hết hiệu lực.

**Bỏ qua được:** bấm **Nộp** khi để trống thì câu đó tính 0 điểm và vẫn ghi vào lịch
sử — không bị hỏi lại ở đề sau. Bài tự viết giới hạn 1000 ký tự.

Mỗi loại là một lượt gọi AI riêng, chạy tuần tự, nên tick cả ba thì chờ lâu hơn.
Một loại hỏng vẫn giữ được các loại còn lại.

**Quiz không đụng tới lịch ôn.** Làm quiz không làm thẻ đến hạn sớm hay muộn đi —
hai thứ cố ý tách rời để khoảng cách ôn không nhảy vì lý do khó lần ra.

## Chạy backend ngoài Docker

Chỉ bật Postgres bằng Docker, app chạy thẳng trên máy:

```bash
docker compose up -d db      # KHÔNG bật api-service, nó chiếm cổng 8080
uv run --directory api-service ielts-api --reload
```

Kiểm tra: `curl http://127.0.0.1:8080/api/health` phải trả `geminiConfigured: true`.

**Không phải setup gì trước.** `uv run` tự dựng venv và cài đúng phiên bản ghi
trong `uv.lock` (file này được commit, nên hai máy chạy ra cùng một bộ). Lần đầu
tốn vài giây, những lần sau tức thì. Đừng `pip install` hay activate venv tay —
đó là cách duy nhất để môi trường lệch nhau.

`app/config.py` (pydantic-settings) khai hai ứng viên `.env` — thư mục gốc repo và
`api-service/` — và cả hai tính từ vị trí file nguồn chứ không phải working
directory, nên gọi từ đâu cũng trúng. Host và cổng lấy từ `SERVER_ADDRESS` /
`SERVER_PORT`, không phải gõ tay.

| Cờ | Ý nghĩa |
|---|---|
| `--reload` | Tự nạp lại khi sửa `.py` trong `app/`. Migration KHÔNG chạy lại mỗi lần reload — nó nằm ở tiến trình cha, trước khi reloader dựng lên |
| `--port` / `--host` | Đè giá trị `.env` cho một lần chạy |
| `--skip-migrate` | Bỏ qua migration khi schema đã chắc chắn ở bản mới nhất |

Sửa file trong `prompts/` thì **không** tự nạp lại, và đó là chủ ý: prompt loader
nhớ kết quả parse trong bộ nhớ tiến trình, còn version prompt thì nằm trong khoá
cache. Phải khởi động lại tay chính là lúc nhớ tăng `version:` ở đầu file.

Nếu `geminiConfigured` vẫn trả `false`, kiểm tra `.env` có nằm ở thư mục gốc repo
không và `GEMINI_API_KEY` đã điền chưa — đó là hai nguyên nhân duy nhất.

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
| `GEMINI_BASE_URL` | endpoint Google | Đổi khi test |
| `GEMINI_TIMEOUT_SECONDS` | `15` | Dịch một từ/câu |
| `GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS` | `30` | Sinh một lô câu hỏi — output dài hơn nên lâu hơn |
| `GEMINI_QUIZ_GRADE_TIMEOUT_SECONDS` | `20` | Chấm một bài tự viết |
| `GEMINI_RETRY_BACKOFF_MS` | `1000` | |
| `TZ` | `Asia/Ho_Chi_Minh` | Quyết định "hôm nay" của lịch ôn. Container mặc định UTC → thiếu biến này thì ngày ôn đổi lúc 07:00 thay vì nửa đêm. **Không dùng được trên Vercel** — xem `APP_TZ` |
| `APP_TZ` | (rỗng) | Tên thứ hai của `TZ`, ưu tiên cao hơn. Chỉ cần trên Vercel: ở đó `TZ` là tên bị nền tảng giữ chỗ (dashboard từ chối tạo) còn Lambda bên dưới tự đặt `TZ=:UTC`, nên không có `APP_TZ` thì lịch ôn im lặng quay về mặc định |
| `AUTH_GOOGLE_CLIENT_ID` | (bắt buộc) | OAuth client kiểu **Web application** |
| `AUTH_GOOGLE_CLIENT_SECRET` | (bắt buộc) | **Chỉ ở backend.** Không bao giờ vào bundle extension |
| `AUTH_ALLOWED_EMAILS` | (rỗng) | Danh sách email được phép, ngăn cách bằng dấu phẩy. **Rỗng = khoá hết** |
| `AUTH_BOOTSTRAP_EMAIL` | (bắt buộc) | Chủ sở hữu dữ liệu cũ. Migration `V6__auth.sql` gán toàn bộ sổ từ hiện có cho email này |
| `AUTH_SESSION_DAYS` | `60` | Hạn phiên, trượt theo mỗi lần dùng |
| `AUTH_DAILY_GEMINI_CALLS` | `300` | Trần lượt gọi AI mỗi người mỗi ngày. `0` = tắt |
| `AUTH_GOOGLE_TOKEN_URL` | endpoint Google | Đổi khi test |
| `AUTH_GOOGLE_AUTH_URL` | endpoint Google | Authorization endpoint của luồng web. Đổi khi test |
| `WEB_BASE_URL` | `http://127.0.0.1:8080` | Origin công khai của web app. Backend dựng `redirect_uri` của luồng đăng nhập web từ đây (**không** từ header `Host`). Phải đăng ký `<WEB_BASE_URL>/api/auth/google/callback` trong Google Cloud Console. Preview deployment của Vercel đổi domain mỗi lần nên đăng nhập web chỉ chạy trên domain production |
| `AUTH_COOKIE_SECURE` | `auto` | `auto` \| `true` \| `false`. `auto` = bật, trừ khi `WEB_BASE_URL` là loopback. Quyết định luôn **tên** cookie: tiền tố `__Host-` cấm cookie không-Secure |
| `DATABASE_URL` | (rỗng) | Rỗng thì ghép từ `DB_*`. Đặt giá trị khi deploy lên Supabase/Vercel, nơi chỉ có một chuỗi kết nối chứ không có năm mảnh rời |
| `VERCEL` | (rỗng) | **Không tự đặt.** Vercel tự gán `1` trong mọi function; backend đọc nó để chuyển sang `NullPool` và tắt prepared statement (bắt buộc với Supavisor transaction mode) |

Phía extension có **ba** file env, và chỉ `.env.example` vào git — hai file kia bị
`.gitignore` chặn nên máy mới clone về phải tự tạo theo mẫu trong đó:

| File | Nạp bởi | Biến |
|---|---|---|
| `apps/extension/.env` | mọi mode | `VITE_GOOGLE_CLIENT_ID` |
| `apps/extension/.env.dev` | `npm run dev`, `npm run build` | `VITE_BACKEND_URL=http://127.0.0.1:8080` |
| `apps/extension/.env.prod` | `npm run build:prod` | `VITE_BACKEND_URL=https://<domain-thật>` |

| Biến | Ghi chú |
|---|---|
| `VITE_GOOGLE_CLIENT_ID` | Cùng giá trị với `AUTH_GOOGLE_CLIENT_ID`. Client **id** công khai được; `client_secret` thì tuyệt đối không |
| `VITE_BACKEND_URL` | Sinh ra **cả** `backendUrl` mặc định trong bundle **lẫn** `host_permissions` trong manifest, nên ràng buộc "ba chỗ phải khớp" rút còn một biến |

### Web app — PWA

Cài được vào màn hình chính và nhận text chia sẻ từ app khác:

| Thứ | Ở đâu |
|---|---|
| `manifest.webmanifest` | `apps/web/public/` — `display: standalone`, icon 192 + 512 (`purpose: "any maskable"`) |
| Service worker | `apps/web/public/sw.js` — viết tay, **không thêm dependency** (Workbox là một dependency mới) |
| Share Target | `share_target` trong manifest → route `/share` → `apps/web/src/share-target.ts` |
| Icon | `npm -w ielts-translator-web run icons` — dùng chung `scripts/make-icons.mjs` với extension |

**Offline chỉ-đọc.** `GET /api/vocab` và `GET /api/stats` dùng stale-while-revalidate; mọi
`/api/*` còn lại là network-only. Cố ý: dịch, ôn và quiz đều đổi trạng thái hoặc tốn quota
Gemini, phục vụ chúng từ cache là nói dối người dùng.

Cache `/api/*` **bị xoá khi đăng xuất** — nó dùng chung theo origin chứ không theo người
dùng, nên bỏ bước đó là trên máy dùng chung người sau thấy sổ từ của người trước.

Service worker **chỉ đăng ký ở bản production**. Ở dev nó cache asset của Vite rồi đánh nhau
với HMR: sửa code mà màn hình không đổi.

**Share Target chỉ có trên Android.** Safari bỏ qua `share_target` một cách im lặng; trên
iOS vẫn cài được vào màn hình chính và vẫn dán tay được.

### Web app (`apps/web/.env`)

Chỉ **một** file, và cả ba biến đều có thể để trống — bản production không cần biết địa chỉ
backend, vì nó chạy **cùng origin** với backend. Mẫu ở `apps/web/.env.example`.

| Biến | Mặc định | Vào bundle? | Ghi chú |
|---|---|---|---|
| `VITE_DEV_PORT` | `5174` | không | Cổng Vite dev server. Không phải 5173 để khỏi tranh cổng với project Vite khác. `strictPort` bật — sai cổng thì báo lỗi chứ không lặng lẽ nhảy sang cổng khác, vì cổng nằm trong redirect URI đã đăng ký với Google |
| `VITE_DEV_BACKEND` | `http://127.0.0.1:8080` | không | Đích proxy `/api/*` lúc dev. Nhờ proxy mà trình duyệt vẫn thấy API cùng origin với trang, nên cookie phiên chạy y như production |
| `VITE_API_BASE_URL` | (rỗng) | **có** | **Để trống.** Rỗng = đường dẫn tương đối `/api/...`, và lúc dev thì `VITE_DEV_BACKEND` lo phần proxy. Đặt sang origin khác sẽ hỏng ở **hai tầng**: CORS chặn preflight ngay (mọi request mang header `X-IELTS-Web`), và kể cả khi mở CORS thì cookie `SameSite=Lax` vẫn không được gửi nên mọi thứ trả 401. App in `console.error` nói rõ cả hai |

Muốn chạy web khác origin với backend thì phải sửa **hai** chỗ phía backend, cả hai hiện
chưa có: mở CORS kèm `allow_credentials=True` (`app/main.py`), và đổi cookie phiên sang
`SameSite=None; Secure` (`app/auth/cookies.py`).

**Đăng nhập lúc dev:** mặc định `WEB_BASE_URL=http://127.0.0.1:8080`, nên Google sẽ trả
người dùng về cổng 8080 chứ không về dev server. Muốn thử luồng đăng nhập ở `npm run dev`
thì đặt `WEB_BASE_URL=http://localhost:5174` trong `.env` gốc **và** đăng ký
`http://localhost:5174/api/auth/google/callback` trong Google Cloud Console.

Vite nạp `.env` trước rồi mới tới file theo mode, nên `.env.dev` / `.env.prod` luôn thắng
`.env`. **Thiếu `.env.prod` thì `build:prod` không báo lỗi** — `VITE_BACKEND_URL` rỗng rơi
về `http://127.0.0.1:8080` và bạn nhận một bundle production trỏ vào localhost. Kiểm bằng
lệnh ở cuối `extension/.env.example` trước khi phát hành.

`api-service/app/config.py` không hardcode giá trị nào — mọi mục đều đọc từ env với
một default, và default trong file chính là cấu hình chạy local. Connection string
được ghép phẳng từ `DB_HOST`/`DB_PORT`/`DB_NAME`, trừ khi `DATABASE_URL` được đặt.

Hai chỗ dễ vấp:

- **`POSTGRES_*` chỉ có tác dụng ở lần khởi tạo data directory đầu tiên.** Đổi
  `DB_NAME`/`DB_USER`/`DB_PASSWORD` khi volume `ielts_pgdata` đã tồn tại thì
  container vẫn chạy với giá trị cũ, còn app thì nối bằng giá trị mới và fail
  xác thực. Muốn đổi thật: `docker compose down -v` — lệnh này **xoá sạch sổ từ
  vựng**, export CSV trước khi chạy.
- **Đổi `GEMINI_*_TIMEOUT_SECONDS` phải đổi kèm ba hằng timeout trong
  `extension/src/background/api-client.ts`.** Extension chờ theo công thức
  `2 × timeout + 1s backoff` (backend thử lại đúng một lần), hiện là 40s / 70s / 50s.
  Đặt thấp hơn thì extension bỏ cuộc trong khi backend vẫn đang xử lý đúng — người
  dùng thấy "backend không trả lời" rồi lần sau thấy đề tự xuất hiện. **Không có
  test nào bắt được khi hai bên lệch.**
- **`DB_PORT`/`APP_PORT` chỉ đổi cổng trên host.** Trong mạng nội bộ của compose
  db luôn là 5432 và api-service luôn là 8080, nên toạ độ database của service
  `api-service` giữ nguyên `db:5432`. Nếu đổi `APP_PORT`, nhớ sửa cả `backendUrl`
  trong trang Options của extension và `host_permissions` trong `manifest.config.ts`.

## Chạy test

```bash
cd api-service && uv run pytest              # KHÔNG cần Docker — pgserver bung Postgres 16 sẵn
cd api-service && uv run mypy app && uv run ruff check .
cd extension && npm test
cd extension && npm run build                # type check chỉ ở đây
```

Lần chạy `pytest` đầu tiên tốn ~10 giây để `initdb`; đặt `PYTEST_PG_DIR` trỏ vào
một thư mục cố định để những lần sau tái dùng data directory đó.

## Chỉnh prompt

Prompt nằm ở `api-service/prompts/*.md`. Sửa xong nhớ tăng `version:` ở đầu file —
cache sẽ tự hết hiệu lực. Rồi `docker compose up -d --build` (hoặc khởi động lại
`ielts-api`: `--reload` cố ý không theo dõi `prompts/`).
