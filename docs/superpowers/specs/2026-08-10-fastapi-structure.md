# Cấu trúc dự án FastAPI — bản để review

**Ngày:** 2026-08-10
**Trạng thái:** ĐỀ XUẤT — chưa viết dòng code nào, đưa ra để bạn duyệt trước
**Kiến trúc:** Supabase (Postgres) + Vercel (FastAPI) + Chrome extension giữ nguyên

---

## 1. Nguyên tắc đặt ra trước

1. **Chia theo tính năng, không chia theo tầng.** Giống hệt `backend/` hiện tại: `auth/`, `vocabulary/`, `srs/`, `quiz/`, `translation/`, `quota/`. Không có `models/`, `services/`, `routers/` gom hết mọi tính năng vào một chỗ — đó là kiểu chia làm mỗi thay đổi phải sờ bốn thư mục.
2. **Giữ nguyên hợp đồng `/api/*`.** Extension không biết backend đã đổi. 217 test phía extension vẫn xanh.
3. **Mỗi tính năng có đúng một `repository.py`.** Đây không phải trang trí: ràng buộc #13 nói mọi truy vấn phải lọc `user_id`, và gom truy vấn về một file là cách duy nhất để `MultiUserIsolationIT` soi được hết.
4. **Chạy song song với Spring trong lúc chuyển.** Thư mục riêng, không đụng `backend/`.

## 2. Cây thư mục

```
ielts-translator/
├── backend/                     # Spring hiện tại — GIỮ NGUYÊN cho tới khi cắt hẳn
├── extension/                   # không đổi, trừ backendUrl
├── supabase/
│   └── migrations/              # V1..V7 chép sang, đổi tên theo timestamp
│       ├── 20260803000001_lookup_cache.sql
│       ├── ...
│       └── 20260810000002_session_token_hash_varchar.sql
└── backend-py/                  # <<< Vercel Root Directory trỏ vào đây
    ├── api/
    │   └── index.py             # điểm vào của Vercel: `from app.main import app`
    ├── app/
    │   ├── main.py              # FastAPI(), CORS, exception handler, include router
    │   ├── config.py            # Settings — MỌI giá trị từ env, không hardcode (ràng buộc #6)
    │   ├── db.py                # engine, session factory, dependency get_db
    │   │
    │   ├── common/
    │   │   ├── errors.py        # ErrorCode, AppError, handler → {code, message, retryable}
    │   │   └── gemini.py        # GeminiClient: 3 mức timeout, retry, map lỗi
    │   │
    │   ├── auth/
    │   │   ├── router.py        # POST /api/auth/google · GET /me · POST /logout
    │   │   ├── service.py       # login / resolve_user_id / logout
    │   │   ├── google.py        # đổi code với Google, đọc payload id_token
    │   │   ├── repository.py    # app_user, user_session
    │   │   ├── models.py        # Pydantic: GoogleLoginRequest, AuthSession, AuthUser
    │   │   └── deps.py          # current_user_id — thay SessionFilter + AuthContext
    │   │
    │   ├── vocabulary/
    │   │   ├── router.py        # POST/GET /api/vocab · GET|DELETE /{id} · /export.csv
    │   │   ├── service.py       # gộp tag, dựng DTO
    │   │   ├── repository.py    # search (ILIKE + tags @>), find_owned, filter_owned_ids
    │   │   ├── models.py
    │   │   └── csv_export.py
    │   │
    │   ├── srs/
    │   │   ├── router.py        # GET /due · GET /stats · POST /review
    │   │   ├── service.py       # hàng đợi due + hạn mức từ mới
    │   │   ├── scheduler.py     # SM-2 — hàm thuần, port thẳng từ SrsScheduler
    │   │   ├── distractors.py   # sinh mồi nhử + validator
    │   │   ├── repository.py
    │   │   └── models.py
    │   │
    │   ├── quiz/
    │   │   ├── router.py        # POST /generate · /answer · /explain
    │   │   ├── service.py
    │   │   ├── generator.py     # 3 loại, find_reusable + prompt_version, xáo lựa chọn
    │   │   ├── grader.py
    │   │   ├── explain.py
    │   │   ├── validator.py     # port từ QuizItemValidator
    │   │   ├── repository.py
    │   │   └── models.py
    │   │
    │   ├── translation/
    │   │   ├── router.py        # POST /api/translate
    │   │   ├── service.py       # cache → quota → Gemini
    │   │   ├── detector.py      # LanguageDetector
    │   │   ├── mode.py          # Mode.of (≤3 token = WORD)
    │   │   ├── prompts.py       # PromptLoader: đọc header `version:`
    │   │   ├── schemas.py       # 4 hình dạng payload cho Gemini
    │   │   ├── cache.py         # LookupCache — CHÚ Ý mục 5
    │   │   ├── repository.py
    │   │   └── models.py
    │   │
    │   ├── quota/
    │   │   ├── guard.py         # consume(user_id) — một câu UPSERT ... RETURNING
    │   │   └── repository.py
    │   │
    │   └── health/router.py     # GET /api/health — CÔNG KHAI, không cần token
    │
    ├── prompts/                 # *.md giữ nguyên, kèm header `version:`
    ├── tests/
    │   ├── conftest.py          # pgserver + chạy migration + seed user (thay AbstractPostgresIT)
    │   ├── test_multi_user_isolation.py   # <<< chốt chặn quan trọng nhất
    │   ├── test_quiz_srs_isolation.py
    │   ├── test_auth_migration.py
    │   ├── test_auth_router.py
    │   ├── test_session_deps.py
    │   ├── test_google_client.py
    │   ├── test_language_detector.py
    │   ├── test_mode.py
    │   ├── test_srs_scheduler.py
    │   ├── test_prompt_loader.py
    │   ├── test_quiz_generator.py
    │   ├── test_quiz_explain.py
    │   └── test_quota_guard.py
    ├── pyproject.toml
    ├── vercel.json
    └── .env.example
```

## 3. Bản đồ Java → Python

| Java hiện tại | FastAPI | Ghi chú |
|---|---|---|
| `SessionFilter` + `AuthContext` (`@RequestScope`) | `auth/deps.py` → `Depends(current_user_id)` | **Sạch hơn hẳn.** Không còn bean phạm vi request, không còn rủi ro ThreadLocal rò giữa hai request |
| `record …Dto` | Pydantic model | Thêm được validate lúc chạy |
| `GlobalExceptionHandler.statusFor()` switch exhaustive | `errors.py` + `@app.exception_handler` | Mất tính exhaustive của compiler — bù bằng test, xem mục 6 |
| `application.yml` `${BIEN:mặc-định}` | `config.py` với `pydantic-settings` | Giữ nguyên TÊN biến môi trường |
| Flyway `V*.sql` | `supabase/migrations/*.sql` | SQL chép nguyên; `${bootstrap_email}` xử lý riêng |
| `@Query` trong repository interface | hàm trong `repository.py` | SQL tường minh, vốn đã gần như vậy |
| `@Transactional` | `with session.begin():` | |
| `@Async` sau commit (mồi nhử) | `BackgroundTasks` + Vercel Cron | Đường lười `request_missing()` đã có sẵn nên rủi ro thấp |
| Testcontainers + `AbstractPostgresIT` | `pgserver` + `conftest.py` | Postgres thật, không cần Docker |
| MockMvc | `httpx.ASGITransport` | Gọi app trong tiến trình, không cần server |

## 4. Bốn quyết định tôi muốn bạn duyệt

**(a) `psycopg` (v3) chứ không `asyncpg`.** asyncpg mặc định dùng prepared statement; Supavisor transaction mode (cổng 6543 — đúng chế độ dành cho serverless) không hỗ trợ. Triệu chứng là lỗi rời rạc dưới tải, loại khó lần nhất. psycopg xử lý sạch hơn và cấu hình rõ ràng hơn.

**(b) SQLAlchemy **sync**, không async.** Mô hình serverless mỗi instance phục vụ một request, nên async không mua được gì về thông lượng, mà lại thêm một lớp để sai. FastAPI chạy endpoint `def` thường trong threadpool, hoàn toàn ổn.

**(c) SQLAlchemy Core/ORM chứ không viết SQL trần.** Vẫn viết SQL tường minh cho các truy vấn phức tạp, nhưng có mapping để `user_id` không bị quên bằng cách nối chuỗi.

**(d) Một Vercel Function duy nhất.** Gói Hobby giới hạn **12 function mỗi lần deploy**; API của bạn có ~17 endpoint. `vercel.json` rewrite tất cả về `api/index.py`:

```json
{
  "regions": ["sin1"],
  "functions": {
    "api/index.py": { "includeFiles": "prompts/**" }
  },
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index" }]
}
```

`includeFiles` là bắt buộc — không có nó thì `prompts/*.md` không được đóng gói, chạy local ngon mà deploy lên là mọi lượt dịch chết.

## 5. Hai chỗ phải port đúng từng chi tiết

**`translation/cache.py`.** Khoá cache ghép theo dạng `độDài:nộiDung|` rồi băm. Lệch một ký tự là **toàn bộ cache hiện có thành rác** — không lỗi nào nổ ra, chỉ là mọi lượt tra đều gọi lại Gemini. Sẽ có test so khoá sinh ra với một giá trị lấy từ DB thật.

**`quiz/generator.py` — `find_reusable` + `prompt_version`.** Đây là cơ chế "không gọi Gemini mỗi lần mở màn quiz" và cách đề cũ tự hết hiệu lực khi sửa prompt. Phần nhiều phán đoán tích luỹ nhất trong cả codebase.

## 6. Chỗ Python yếu hơn Java, và cách bù

`switch` exhaustive của Java bắt được lúc biên dịch khi thêm `ErrorCode` hay `QuizType` mới mà quên xử lý. Python không có. Bù bằng ba thứ:

- `mypy --strict` trong CI
- `assert_never()` ở cuối mỗi chỗ rẽ nhánh theo enum — mypy sẽ báo khi thiếu nhánh
- một test duyệt qua từng giá trị enum và khẳng định có ánh xạ

## 7. Phụ thuộc — mỗi cái một lý do (ràng buộc #12)

| Gói | Vì sao |
|---|---|
| `fastapi` | framework |
| `pydantic` / `pydantic-settings` | DTO + cấu hình từ env |
| `sqlalchemy` | truy cập DB |
| `psycopg[binary]` | driver — xem 4(a) |
| `httpx` | gọi Gemini và Google |
| dev: `pytest`, `pgserver`, `mypy`, `ruff` | `pgserver` cho Postgres thật mà không cần Docker |

Không dùng `supabase-py`: mình nối thẳng Postgres bằng JDBC-tương-đương, không cần PostgREST.

## 8. Ngoài phạm vi bản chuyển này

- Không bật RLS (backend là server đáng tin, giữ nguyên cách lọc `user_id`). Có thể thêm sau như lớp thứ hai.
- Không dùng Supabase Auth — thiết kế auth hiện tại port 1:1.
- Không đổi hợp đồng API, không đổi schema.
- Không đổi extension ngoài `backendUrl`.
