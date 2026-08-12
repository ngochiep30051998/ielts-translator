# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Ngôn ngữ

Comment code, message lỗi, text hiển thị và trả lời người dùng viết bằng **tiếng Việt đủ dấu** (đúng như code hiện tại). Tên class/biến/hàm/module giữ tiếng Anh. Lưu UTF-8.

## Lệnh thường dùng

```bash
# Backend (cwd = api-service/)
uv run pytest                                   # KHÔNG cần Docker — pgserver bung Postgres 16 sẵn
uv run pytest tests/test_language_detector.py   # một file test
uv run mypy app && uv run ruff check .          # TYPE CHECK CHỈ Ở ĐÂY
uv run ielts-api --reload                       # chạy local, cần `docker compose up -d db`

# Extension (cwd = extension/)
npm test                              # vitest run
npm test -- src/content/selection.test.ts   # một file test
npm run build                         # mode `dev` → backend localhost. TYPE CHECK CHỈ Ở ĐÂY
npm run build:prod                    # mode `prod` → backend domain thật, bản đem phát hành
npm run icons                         # sinh lại public/icons/* từ scripts/make-icons.mjs

# Chạy hệ thống (cwd = thư mục gốc)
docker compose up -d --build          # toàn bộ backend + Postgres + Caddy
docker compose up -d db               # chỉ Postgres, app chạy bằng `uv run ielts-api --reload`
curl http://127.0.0.1:8080/api/health # phải trả geminiConfigured: true
```

**Luôn gọi qua `uv run`**, đừng `pip install` hay activate venv bằng tay: `uv run` tự dựng venv theo đúng `uv.lock` đã commit, nên hai máy không bao giờ lệch phiên bản.

`uv run mypy app` là nơi **duy nhất** chạy type check phía backend, `npm run build` là nơi duy nhất phía extension. Test xanh mà mypy/build đỏ vẫn là hỏng — luôn chạy cả hai trước khi báo xong.

pytest chỉ nhặt file khớp `test_*.py` trong `tests/` (khai tường minh ở `[tool.pytest.ini_options]`). Đặt sai tên file test = test bị bỏ qua **im lặng**.

**Không bao giờ chạy `docker compose down -v`** — xoá volume `ielts_pgdata`, tức xoá sạch sổ từ vựng của **mọi người dùng**, không riêng ai. Cần reset DB thì hỏi trước và nhắc export CSV (`GET /api/vocab/export.csv`). Trên VPS phải có `pg_dump` hằng ngày trước khi đưa người thứ hai vào dùng.

## Kiến trúc

Chrome extension MV3 (`extension/`) gọi FastAPI ở `127.0.0.1:8080` (`api-service/`), backend gọi Gemini. Chạy được cả hai đường: local/VPS qua Docker Compose + Caddy, hoặc serverless trên Vercel qua `api/index.py`.

Bản Spring Boot cũ (`backend/`) **đã bị xoá** sau khi port xong — còn trong lịch sử git nếu cần tra. Đừng dựng lại đường Java song song.

**Đường dữ liệu một lượt dịch:**

```
content/selection.ts (validate + trích context)
  → content/index.ts (bubble trong Shadow DOM)
  → shared/messages.ts (union type ExtensionRequest)
  → background/service-worker.ts
  → background/api-client.ts (fetch)
  → translation/router.py → translation/service.py
       → detector.py (EN_VI | VI_EN) + Mode (WORD nếu ≤3 token, else SENTENCE)
       → prompts.py chọn prompts/{en-vi|vi-en}-{word|sentence}.md
       → cache.py (hit → trả luôn) hoặc common/gemini.py + lưu cache
```

Bốn tổ hợp direction × mode sinh ra **bốn hình dạng payload JSON khác nhau** (`translation/schemas.py` phía backend, `shared/types.ts` phía extension). Mọi UI hiển thị kết quả phải phân nhánh theo `direction` + `mode`.

**Backend** — package theo feature dưới `api-service/app/`: `common` (`errors.py`, `gemini.py`, `schema.py`), `health`, `auth`, `translation`, `vocabulary`, `srs`, `quiz`, `quota`. Python 3.12, FastAPI + Pydantic v2 + pydantic-settings, SQLAlchemy 2.0 **sync** + psycopg3 + Postgres 16, `mypy --strict` + ruff. Migration chạy bằng `app/migrator.py` (thay Flyway), khởi động một lần qua `app/startup.py`.

**Extension** — bốn surface (`content/`, `background/`, `sidepanel/`, `options/`) + `shared/`. React 18 + TS 5.7 (`strict` **và** `noUnusedLocals`), Vite 5 + `@crxjs/vite-plugin`, manifest sinh từ `manifest.config.ts` (không có `manifest.json` viết tay). **Không có thư viện UI/state nào** — CSS viết tay (`sidepanel/styles.css`, CSS-in-TS ở `content/bubble.css.ts`). Test: Vitest + RTL + jsdom; `vitest.setup.ts` stub sẵn `chrome.storage.local`/`runtime`/`sidePanel` — cần API chrome mới thì bổ sung vào stub đó, đừng stub rải rác.

## Ràng buộc — vi phạm là hỏng thật, không phải vấn đề phong cách

1. **Content script / side panel / Options KHÔNG BAO GIỜ gọi HTTP.** Mọi request đi qua service worker (`background/api-client.ts`). `host_permissions` chỉ cấp cho extension context; content script chạy trong origin của trang lạ.

2. **Hợp đồng message ở `shared/messages.ts`.** Luồng mới = thêm interface request + thêm vào union `ExtensionRequest` + thêm vào `ResponseMap`, rồi mới xử lý ở service worker. Không gửi message ad-hoc bằng object rời.

3. **`shared/types.ts` là bản gương của model backend.** Backend đổi field → sửa ở đây trước, TypeScript sẽ chỉ ra mọi chỗ vỡ. Đừng bịa field backend không có.

4. **Lỗi đi một đường duy nhất, hình dạng `{ code, message, retryable }`.** Backend: ném `AppError.of(ErrorCode.X, "thông điệp tiếng Việt")`, `status_for()` trong `common/errors.py` map sang HTTP status. Mã hợp lệ: `GEMINI_QUOTA`, `GEMINI_UNAVAILABLE`, `PARSE_ERROR`, `TEXT_TOO_LONG`, `NOT_FOUND`, `UNAUTHORIZED`, `FORBIDDEN`, `AUTH_UNAVAILABLE`, `INTERNAL`. UI phải phân biệt lỗi retry được và lỗi vĩnh viễn.

   Python không có `switch` exhaustive như Java, nên chỗ này có **ba lớp bù**: `assert_never(code)` ở cuối `status_for`, `test_error_code_mapping.py` duyệt từng giá trị enum, và `mypy --strict`. **Đừng thêm nhánh `case _`/`else` để né** — nó làm cả ba lớp mù cùng lúc.

5. **Sửa nội dung prompt PHẢI tăng `version:` ở đầu file `api-service/prompts/*.md`.** Version nằm trong cache key — đó là cách duy nhất làm cache cũ hết hiệu lực. Cache key = text + context + direction + mode + model + prompt version, nối theo dạng `độDài:nộiDung|`; đừng đổi cách nối mà chưa đọc docstring `_append_field` trong `translation/cache.py`. Sửa file trong `prompts/` **không** kích hoạt `--reload` (cố ý): phải khởi động lại tay, và đó chính là lúc nhớ tăng `version:`.

6. **Không hardcode cấu hình trong code** — mọi thứ đọc qua `app/config.py` (pydantic-settings), default trong file đó chính là cấu hình chạy local. Thêm config mới → thêm vào `.env.example` **và** bảng "Biến môi trường" trong `README.md`. Tên biến giữ nguyên bộ chung của cả dự án; connection string ghép phẳng từ `DB_HOST`/`DB_PORT`/`DB_NAME`, trừ khi `DATABASE_URL` được đặt (Supabase/Vercel chỉ đưa một chuỗi).

7. **CORS chỉ mở cho `EXTENSION_ID`** (`app/main.py`). ID cố định nhờ field `key` trong `manifest.config.ts` + `key.pem` — đừng xoá, đừng tái sinh, đừng in `key.pem` ra chat. ID đổi → `.env` sai → backend chặn CORS → cả extension chết.

8. **Migration là append-only.** Không sửa file `api-service/migrations/V*.sql` đã chạy; thêm version mới, và cập nhật model SQLAlchemy trong cùng thay đổi. `migrator.py` nhận biết cả `flyway_schema_history` cũ nên schema dựng từ bản Java vẫn dùng tiếp được — đừng đánh số lại.

9. **Giới hạn 1500 ký tự chặn ở cả hai phía** (`translation/service.py: MAX_TEXT_LENGTH` và `shared/text.ts`). Đổi số thì đổi đồng bộ.

10. **`host_permissions` và `backendUrl` mặc định sinh từ ĐÚNG MỘT biến** — `VITE_BACKEND_URL`, đọc qua `loadEnv` ở `manifest.config.ts` (đường Node) và qua `import.meta.env` ở `shared/settings.ts` (đường bundle); `shared/backend-url.ts` là nguồn chung. Chỗ còn lại phải tự đảm bảo là domain thật đang chạy. Options là ô nhập tự do nhưng Chrome chỉ cho gọi origin đã khai trong manifest — trỏ sang domain chưa khai thì request chết **im lặng**, không lỗi mạng, không lỗi CORS.

    Biến đó tách theo mode: `.env.dev` (dùng bởi `npm run dev` / `npm run build`) và `.env.prod` (dùng bởi `npm run build:prod`). **Cả hai đều bị `.gitignore` chặn** — mẫu nằm ở `extension/.env.example`. Thiếu `.env.prod` thì `build:prod` không báo lỗi, chỉ lặng lẽ cho ra bundle production trỏ localhost.

11. **Bubble render trong Shadow DOM** (`content/bubble.ts`) — cách duy nhất tránh CSS trang chủ đè lên. Đừng chèn thẳng vào DOM trang hay thêm `<link>` toàn cục.

12. **Không thêm dependency mới** nếu chưa nêu lý do và được đồng ý. Dự án cố ý gọn: backend đúng 7 dependency runtime (xem comment "mỗi phụ thuộc một lý do" trong `pyproject.toml`), extension chỉ React + Vite + Vitest. Đăng nhập Google **không** thêm dependency nào: backend tự đổi `code` với Google qua `httpx`, và vì token đến thẳng từ token endpoint qua TLS nên không phải verify chữ ký (xem `auth/google.py`). Nếu ai đó đổi sang nhận `id_token` từ client thì **bắt buộc** phải verify RS256 qua JWKS — lúc đó mới bàn tới thư viện.

    `psycopg[binary]` chứ không `asyncpg`: asyncpg mặc định dùng prepared statement, mà Supavisor ở transaction mode không hỗ trợ. Triệu chứng là lỗi rời rạc dưới tải — loại khó lần nhất.

13. **Mọi truy vấn chạm dữ liệu học PHẢI lọc theo `user_id`.** Chủ sở hữu nằm ở đúng một cột — `vocab_entry.user_id`; mọi bảng khác treo vào nó. Quên một mệnh đề `WHERE user_id = ?` không làm gì đỏ cả, nó chỉ lặng lẽ cho người này đọc dữ liệu người kia. Chốt chặn là `tests/test_multi_user_isolation.py`: **endpoint mới không có mặt trong file đó là endpoint chưa được chứng minh an toàn**. Id nhận từ client (`vocabIds`, `quizItemId`, `cardId`, `/vocab/{id}`) phải tra theo `(id, user_id)` và trả `NOT_FOUND` — không phải `FORBIDDEN`, vì 403 xác nhận id đó có tồn tại. User id lấy qua `Depends(current_user_id)` (`auth/deps.py`), không phải trạng thái toàn cục.

14. **`lookup_cache` CỐ Ý không có `user_id`.** Nó là cache bản dịch của một chuỗi công khai; dùng chung là phần tiết kiệm quota Gemini lớn nhất của hệ thống. "Sửa cho nhất quán" sẽ làm `test_lookup_cache_co_y_dung_chung` đỏ.

15. **Đường Vercel và đường Docker phải khớp nhau.** `vercel.json` rewrite MỌI đường dẫn về `api/index.py` (gói Hobby giới hạn 12 function/deploy), và `includeFiles` là **bắt buộc** — thiếu nó thì `prompts/*.md` không được đóng gói, chạy local ngon mà deploy lên là mọi lượt dịch chết. `test_deploy_readiness.py` và `test_vercel_entry.py` giữ chỗ này. Migration **không** chạy lúc cold start (nhiều instance cùng `ALTER TABLE` là công thức để khoá lẫn nhau) — trên Supabase chạy `migrations/V*.sql` một lần bằng tay.

## Quy ước test

- **Backend**: tất cả ở `api-service/tests/`, tên `test_*.py`. **Không cần Docker** — `pgserver` bung nhị phân Postgres 16 thật (lần chạy đầu tốn ~10s để `initdb`; đặt `PYTEST_PG_DIR` trỏ vào thư mục cố định để tái dùng). Gemini và Google được giả lập bằng transport giả của httpx, chặn ở tầng vận chuyển nên vẫn chạy qua đúng code dựng body và map lỗi.
- **Extension**: test đặt cạnh file được test (`Options.test.tsx` cạnh `Options.tsx`). Query theo vai trò/nhãn người dùng thấy (RTL), đừng bám class CSS hay cấu trúc DOM.
- Dùng skill `superpowers:test-driven-development` khi viết code, `superpowers:systematic-debugging` khi sửa bug, `superpowers:verification-before-completion` trước khi báo xong. Không nói "đã xong / đã fix / test pass" khi chưa dán được output lệnh thật.

## Bẫy cấu hình đã biết

- **`POSTGRES_*` chỉ có tác dụng lần khởi tạo data directory đầu tiên.** Đổi `DB_NAME`/`DB_USER`/`DB_PASSWORD` khi volume đã tồn tại → container giữ giá trị cũ, app nối bằng giá trị mới và fail xác thực.
- **`DB_PORT`/`APP_PORT` chỉ đổi cổng publish trên host.** Trong mạng compose db luôn 5432, api-service luôn 8080.
- **`--reload` không nạp lại `prompts/`.** `PromptLoader` nhớ kết quả parse trong bộ nhớ tiến trình. Sửa prompt thì khởi động lại tay.
- **`reload_dirs` cố ý chỉ trỏ `app/`.** Không giới hạn thì watcher soi cả `.venv` (hàng chục nghìn file) và trên macOS chạm trần số file mở được.
- **Trên Vercel múi giờ đặt bằng `APP_TZ`, không phải `TZ`.** `TZ` là tên bị nền tảng giữ chỗ — dashboard từ chối tạo ("The name of your Environment Variable is reserved") trong khi Lambda bên dưới tự đặt `TZ=:UTC` (dạng POSIX, không phải key IANA). `config.py` nhận cả hai tên qua `AliasChoices("APP_TZ", "TZ")` và bỏ qua mọi giá trị bắt đầu bằng `:`. Đừng "sửa gọn" thành cắt dấu `:` lấy `UTC`: chuỗi đó hợp lệ nên lịch ôn lệch 7 tiếng mà không lỗi gì. `tzdata` nằm trong dependency runtime vì cùng lý do — `zoneinfo` đọc file hệ thống, image serverless không đảm bảo có.
- **`VERCEL=1` do Vercel tự gán, đừng tự đặt.** `api-service` đọc nó để chuyển sang `NullPool` và tắt prepared statement — bắt buộc với Supavisor transaction mode.

## Ranh giới làm việc

- **Không tự commit/push/tạo PR** trừ khi người dùng yêu cầu.
- Ranh giới `api-service/` ↔ `extension/` tách sạch: thay đổi chạm cả hai phía thì **chốt hợp đồng API trước** (tên field, kiểu, status code, mã lỗi) rồi mới sửa song song.
- Repo có 5 agent chuyên trách (`.claude/agents/`: `pm`, `techlead`, `senior-backend`, `senior-frontend`, cộng `senior-ba` global) và skill `team` điều phối. Việc nhỏ, một phía, đã rõ phải làm gì → tự làm, đừng gọi team.
