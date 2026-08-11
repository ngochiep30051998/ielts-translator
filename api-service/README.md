# api-service — backend FastAPI

Backend **duy nhất** của dự án. Bản Spring Boot cũ (`backend/`) đã bị xoá sau khi port xong
và `Caddyfile` được trỏ sang đây — lịch sử của nó còn trong git nếu cần tra.

Hợp đồng `/api/*`, schema database và bộ biến môi trường giữ nguyên như bản Java, nên
extension không phải đổi gì.

## Chạy

**Không phải setup gì cả.** `uv run` tự dựng venv, tự cài đúng phiên bản trong `uv.lock`,
rồi chạy — không cần `uv venv`, không cần `source .venv/bin/activate`, và không cần nhớ
đường dẫn `.venv/bin/python`. Máy chưa có venv thì lệnh đầu tiên tốn vài giây; những lần
sau tức thì.

Chạy local, dùng Postgres của `docker compose up -d db`:

```bash
uv run ielts-api --reload
```

Chạy được từ thư mục gốc repo, khỏi `cd`:

```bash
uv run --directory api-service ielts-api --reload
```

Mọi lệnh khác cũng đi qua `uv run` nên không bao giờ lệch môi trường:

```bash
uv run pytest
```

```bash
uv run mypy app && uv run ruff check .
```

`uv.lock` được commit — hai máy chạy `uv run` sẽ cài đúng cùng một bộ phiên bản. Đó là thứ
`uv pip install` không bảo đảm được.

Vẫn dùng được dạng dài nếu muốn (tương đương hệt):

```bash
.venv/bin/python -m app --reload
```

Lệnh đó chạy migration một lần rồi lên server. Host và cổng lấy từ `SERVER_ADDRESS` /
`SERVER_PORT` trong `.env` ở thư mục gốc repo — không phải gõ tay, và không có chỗ nào để
cấu hình lệch với `docker-compose.yml`.

```bash
.venv/bin/python -m app --help
```

| Cờ | Ý nghĩa |
|---|---|
| `--reload` | Tự nạp lại khi sửa `.py` trong `app/`. Migration KHÔNG chạy lại mỗi lần reload — nó nằm ở tiến trình cha, trước khi reloader dựng lên |
| `--port` / `--host` | Đè giá trị `.env` cho một lần chạy |
| `--skip-migrate` | Bỏ qua migration khi schema đã chắc chắn ở bản mới nhất |

`reload_dirs` cố ý chỉ trỏ vào `app/`: không giới hạn thì watcher soi cả `.venv` (hàng chục
nghìn file) và trên macOS sẽ chạm trần số file mở được.

Sửa file trong `prompts/` thì **không** tự nạp lại, và đó là chủ ý — `PromptLoader` nhớ kết
quả parse trong bộ nhớ tiến trình, còn version prompt thì nằm trong khoá cache. Phải khởi
động lại tay chính là lúc nhớ tăng `version:` ở đầu file (ràng buộc #5).

Chạy bằng Docker (từ thư mục gốc repo):

```bash
docker compose up -d --build
```

```bash
curl 127.0.0.1:8080/api/health
```

## Test

```bash
pytest
```

`pgserver` bung sẵn nhị phân PostgreSQL 16 nên **test không cần Docker**. Lần chạy đầu tốn
~10 giây để `initdb`; đặt `PYTEST_PG_DIR` trỏ vào một thư mục cố định để những lần sau tái
dùng data directory đó.

```bash
mypy app && ruff check .
```

`mypy --strict` không phải để cho đẹp: thêm một `ErrorCode` mới mà quên nhánh xử lý là loại
lỗi Python không tự bắt được. `assert_never()` + mypy + `test_error_code_mapping.py` là ba
lớp bù cho chỗ đó — đừng thêm `case _`/`else` để né, nó làm cả ba mù cùng lúc.

## Bố cục

Chia theo tính năng:

```
app/
├── main.py          FastAPI, CORS, exception handler
├── config.py        Settings từ env — GIỮ NGUYÊN tên biến của .env dùng chung
├── db.py            engine + session, SQLAlchemy sync + psycopg3
├── migrator.py      chạy migrations/V*.sql; nhận biết flyway_schema_history do bản Java để lại
├── startup.py       chạy migration một lần rồi thoát
├── common/          errors.py · gemini.py · schema.py
├── auth/            router · service · google · repository · deps · models
├── vocabulary/      router · service · repository · csv_export · models
├── srs/             router · service · scheduler (SM-2) · distractors · card_creator
├── quiz/            router · service · generator · grader · explain · validator · candidates
├── translation/     router · service · detector · prompts · schemas · cache
├── quota/           guard · repository
└── health/router.py
migrations/          V1..V7, append-only — SQL thuần, không sinh ra bởi ORM
prompts/             *.md kèm header `version: N`
api/index.py         điểm vào Vercel
```

## Vì sao nó trông như thế này (di sản từ bản Java)

Thư mục này là bản port 1:1 của một backend Spring Boot. Vài lựa chọn chỉ có nghĩa khi biết
điều đó — chép lại đây để đừng ai "dọn dẹp" nhầm:

| Bản Java | Ở đây | Vì sao |
|---|---|---|
| `SessionFilter` + bean `@RequestScope` | `Depends(current_user_id)` | Không còn trạng thái theo thread để rò giữa hai request |
| `VocabEntrySavedEvent` + `@EventListener` | gọi thẳng `tao_the_khi_luu_tu()` | Listener đồng bộ trong cùng transaction đúng bằng một lời gọi hàm |
| `@Async` + `ThreadPoolTaskExecutor` | `BackgroundTasks` | |
| Flyway | `app/migrator.py` | SQL giữ dạng thuần; `migrator.py` đọc được cả `flyway_schema_history` cũ nên schema dựng từ bản Java dùng tiếp được, không cần đánh số lại |
| Testcontainers | `pgserver` | Postgres 16 thật, không cần Docker |
| MockMvc | `TestClient` | Gọi app trong tiến trình |
| WireMock | transport giả của httpx | Chặn ở tầng vận chuyển nên vẫn chạy qua đúng code dựng body và map lỗi |

## Deploy Vercel

`vercel.json` rewrite MỌI đường dẫn về `api/index.py`: gói Hobby giới hạn 12 function mỗi
lần deploy, mà API có nhiều endpoint hơn thế.

`includeFiles` là **bắt buộc** — không có nó thì `prompts/*.md` không được đóng gói, chạy
local ngon mà deploy lên là mọi lượt dịch chết.

Migration KHÔNG chạy lúc cold start (nhiều instance cùng `ALTER TABLE` là công thức để khoá
lẫn nhau). Trên Supabase, chạy `migrations/V*.sql` một lần bằng tay.
