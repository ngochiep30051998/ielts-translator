# api-service — bản port FastAPI của `backend/`

Cùng một hợp đồng `/api/*`, cùng một schema database, cùng một bộ biến môi trường. Extension
không biết nó đang nói chuyện với bên nào.

`backend/` (Spring Boot) **vẫn là bản đang phục vụ thật**. Thư mục này chạy song song để
đối chiếu, và chỉ trở thành bản chính khi `Caddyfile` được trỏ sang nó.

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
`SERVER_PORT` trong `.env` **dùng chung với backend Spring** — không phải gõ tay, và không
có chỗ nào để hai bên lệch nhau.

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

Chạy bằng Docker cùng lúc với backend Spring — hai cổng, một database:

```bash
docker compose up -d --build db app api-service
```

```bash
curl 127.0.0.1:8080/api/health && curl 127.0.0.1:8081/api/health
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

`mypy --strict` không phải để cho đẹp: Java bắt được lúc biên dịch khi thêm `ErrorCode` mới
mà quên nhánh xử lý, còn Python thì không. `assert_never()` + mypy là phần bù cho chỗ đó.

## Bố cục

Chia theo tính năng, phản chiếu đúng `backend/src/main/java/.../`:

```
app/
├── main.py          FastAPI, CORS, exception handler
├── config.py        Settings từ env — GIỮ NGUYÊN tên biến của application.yml
├── db.py            engine + session, SQLAlchemy sync + psycopg3
├── migrator.py      thay Flyway; nhận biết flyway_schema_history có sẵn
├── startup.py       chạy migration một lần rồi thoát
├── common/          errors.py · gemini.py · schema.py
├── auth/            router · service · google · repository · deps · models
├── vocabulary/      router · service · repository · csv_export · models
├── srs/             router · service · scheduler (SM-2) · distractors · card_creator
├── quiz/            router · service · generator · grader · explain · validator · candidates
├── translation/     router · service · detector · prompts · schemas · cache
├── quota/           guard · repository
└── health/router.py
migrations/          V1..V7 chép NGUYÊN VĂN từ backend/
prompts/             *.md chép nguyên, kèm header `version: N`
api/index.py         điểm vào Vercel
```

## Khác biệt có chủ ý so với bản Java

| Java | Python | Vì sao |
|---|---|---|
| `SessionFilter` + bean `@RequestScope` | `Depends(current_user_id)` | Không còn trạng thái theo thread để rò giữa hai request |
| `VocabEntrySavedEvent` + `@EventListener` | gọi thẳng `tao_the_khi_luu_tu()` | Listener đồng bộ trong cùng transaction đúng bằng một lời gọi hàm |
| `@Async` + `ThreadPoolTaskExecutor` | `BackgroundTasks` | |
| Flyway | `app/migrator.py` | SQL giữ nguyên dạng thuần để `diff` với `backend/` được |
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
