# Kiến trúc backend FastAPI theo DDD — bản để review

**Ngày:** 2026-08-10
**Trạng thái:** ĐỀ XUẤT
**Thay cho:** `2026-08-10-fastapi-structure.md` (bản chia theo tính năng đơn giản)

---

## 1. Đánh giá thẳng: DDD hợp chỗ nào, không hợp chỗ nào

DDD trả lãi khi có **nghiệp vụ phức tạp thật**, có **chuyên gia nghiệp vụ tách khỏi lập trình
viên**, và có **đội đông cần ranh giới**. Dự án này có một trong ba: nghiệp vụ có chỗ phức
tạp thật. Hai cái còn lại thì không — bạn vừa là chuyên gia vừa là người viết, và đội có một
người.

Nên tôi lấy phần chiến thuật của DDD chỗ nó tự trả lãi, và **cố ý bỏ** phần còn lại.

**Lấy — vì có lãi thật:**

| Thành phần | Vì sao ở dự án NÀY |
|---|---|
| **Bounded context** | Bạn **đã** làm rồi mà chưa gọi tên: `quiz` cố ý không import gì từ `srs`, và `QuizSrsIsolationIT` canh điều đó. Đó đúng là quan hệ upstream/downstream có ACL |
| **Value Object** | Chỗ lãi cao nhất — xem mục 4. `Email` tự hạ chữ thường sẽ **xoá hẳn** lớp lỗi mà tôi phải cảnh báo trong checklist |
| **Aggregate giữ bất biến** | `Session` và `SrsCard` hiện để bất biến rải rác ở service và câu truy vấn. Đưa vào aggregate là làm trạng thái sai trở nên không biểu diễn được |
| **Port & Adapter** | Domain không import framework → **test được không cần Postgres**. Rất đáng ở đây vì phần deploy tôi không kiểm chứng được |
| **ACL quanh Gemini** | Hôm nay `JsonNode.path()` rải hiểu biết về hình dạng JSON của Gemini khắp `QuizService` |

**Bỏ — vì sẽ là nghi lễ:**

| Thành phần | Vì sao bỏ |
|---|---|
| CQRS, read model tách riêng | Không có vấn đề quy mô nào để giải |
| Domain event + event bus | Toàn hệ thống có đúng một sự kiện (`VocabEntrySavedEvent`), và serverless không có tiến trình dài để chạy bus |
| DTO ánh xạ ở mọi tầng | Mệt mỏi ánh xạ, đổi lại không được gì cho một người viết |
| DB riêng cho mỗi context | Một Postgres, khoá ngoại đi qua context — chấp nhận có ý thức |
| Specification pattern, Factory cho mọi thứ | Truy vấn của bạn đơn giản; `sqlalchemy` đã đủ diễn đạt |

**Cái giá:** số file tăng khoảng gấp đôi, và ước lượng chuyển từ **17–23 ngày lên 22–30 ngày**.

## 2. Bản đồ context

```
        ┌──────────────┐
        │   identity   │  (User, Session)
        └──────┬───────┘
               │ user_id
   ┌───────────┼───────────┬──────────────┐
   ▼           ▼           ▼              ▼
┌────────┐ ┌────────┐ ┌─────────┐  ┌────────────┐
│vocabu- │ │  srs   │ │  quiz   │  │translation │
│ lary   │◄┤        │ │         │  │            │
└────────┘ └───┬────┘ └────┬────┘  └────────────┘
               │  CHỈ ĐỌC  │
               └───────────┘
                 qua ACL
```

- `vocabulary` là **upstream** của `srs` và `quiz` — cả hai treo vào `vocab_entry`.
- `quiz` đọc dữ liệu SRS qua **một read model duy nhất** (`QuizCandidateReadModel`) và
  **không bao giờ ghi**. Đây là bất biến đã có, `test_quiz_srs_isolation.py` giữ nguyên vai
  trò chứng minh.
- `translation` gần như độc lập; `lookup_cache` cố ý **không thuộc về user nào**.
- `quota` là context nhỏ chứa đúng một luật: trần lượt gọi AI mỗi người mỗi ngày.

## 3. Bốn tầng và luật đi một chiều

```
interface/        FastAPI router, Pydantic schema, mã HTTP
    ↓ gọi
application/      use case — điều phối, mở transaction
    ↓ gọi
domain/           entity, value object, domain service, PORT (Protocol)
    ↑ hiện thực
infrastructure/   SQLAlchemy repo, HTTP client, ACL
```

**Luật:** `domain/` **không được import** `fastapi`, `sqlalchemy`, `pydantic`, `httpx`,
`psycopg`. Chỉ thư viện chuẩn.

Đây không phải lời hứa suông — nó là một test:

```python
# tests/test_architecture.py
FORBIDDEN = {"fastapi", "sqlalchemy", "pydantic", "httpx", "psycopg", "app.infrastructure"}

def test_domain_khong_phu_thuoc_framework():
    """
    DDD làm nửa vời còn tệ hơn không làm: thư mục tên `domain/` mà bên trong là entity
    SQLAlchemy thì trông như kỷ luật nhưng không cho kỷ luật nào. Đây là phép thử duy
    nhất phân biệt hai thứ đó, và nó chạy được.
    """
    for path in Path("app/contexts").glob("*/domain/**/*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            ...  # bắt mọi Import / ImportFrom nằm trong FORBIDDEN
```

Cùng tinh thần với `QuizSrsIsolationIT`: bất biến kiến trúc được **chứng minh**, không phải
được nhắc trong tài liệu.

## 4. Value Object — chỗ lãi cao nhất

Đây là phần tôi tin tưởng nhất, vì mỗi VO xoá bỏ một lớp lỗi **có thật** trong lịch sử dự án.

```python
@dataclass(frozen=True, slots=True)
class Email:
    """
    Hạ chữ thường ngay lúc dựng.

    Xoá hẳn lớp lỗi mà checklist bàn giao phải cảnh báo bằng lời: AUTH_BOOTSTRAP_EMAIL gõ
    tay trong .env lệch hoa thường so với email Google trả về → tạo tài khoản thứ hai →
    toàn bộ sổ từ cũ nằm ở tài khoản không ai đăng nhập được. Có VO thì không còn chỗ nào
    để quên `IgnoreCase`.
    """
    value: str
    def __post_init__(self):
        object.__setattr__(self, "value", self.value.strip().lower())
        if "@" not in self.value:
            raise ValueError("email không hợp lệ")


@dataclass(frozen=True, slots=True)
class TokenHash:
    """
    Chỉ dựng được từ SessionToken. Không có đường nào lưu token thô xuống DB, vì repository
    chỉ nhận TokenHash — hệ kiểu chặn, không phải code review chặn.
    """
    value: str
    @staticmethod
    def of(token: "SessionToken") -> "TokenHash":
        return TokenHash(hashlib.sha256(token.value.encode()).hexdigest())


@dataclass(frozen=True, slots=True)
class CacheKey:
    """
    Ghép theo dạng `độDài:nộiDung|` rồi băm. Lệch một ký tự là TOÀN BỘ cache hiện có thành
    rác — không lỗi nào nổ ra, chỉ là mọi lượt tra gọi lại Gemini.

    Là VO nên quy tắc ghép nằm ở ĐÚNG MỘT chỗ và có test riêng so với giá trị lấy từ DB
    thật. Ở bản Java nó là một method private trong TranslationService.
    """
```

Thêm: `EaseFactor` (chặn trong 1.3–2.5), `IntervalDays` (không âm), `PromptVersion`,
`GoogleSub`, `UserId`.

## 5. Aggregate giữ bất biến

**`Session`** — hôm nay ba điều kiện "còn sống" nằm trong câu truy vấn JPA (`revoked_at is
null and expires_at > now`), tức là quên một cái ở tầng service thì token đã thu hồi vẫn
dùng được:

```python
@dataclass
class Session:
    def is_alive(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now

    def touch(self, now: datetime, ttl: timedelta) -> None:
        """Trượt hạn, nhưng ghi tối đa MỘT lần mỗi ngày — ngưỡng nằm trong aggregate."""
```

**`SrsCard`** — SM-2 chuyển từ `SrsScheduler` (service sửa entity từ bên ngoài) vào chính
aggregate:

```python
def review(self, rating: Rating, today: date) -> ReviewOutcome:
    """Trả về trạng thái mới + bản ghi log. Không ai đặt được ease_factor ngoài khoảng."""
```

**`QuizItem`** — `is_reusable(prompt_version)` gói luật "chưa có lượt làm nào và version
prompt còn hiệu lực".

Chú ý: `SrsScheduler` hiện tại đã là **hàm thuần có test riêng**. Chuyển vào aggregate là
đổi chỗ đặt, không phải viết lại — test port gần như nguyên.

## 6. Cây thư mục

```
backend-py/
├── api/index.py                        # điểm vào Vercel
├── app/
│   ├── main.py                         # FastAPI, CORS, exception handler
│   ├── config.py                       # Settings từ env
│   ├── shared/
│   │   ├── domain/errors.py            # DomainError, ErrorCode — KHÔNG biết HTTP
│   │   ├── domain/value_objects.py     # UserId, Email
│   │   └── infrastructure/db.py        # engine, unit of work
│   └── contexts/
│       ├── identity/
│       │   ├── domain/
│       │   │   ├── model.py            # User, Session (aggregate root)
│       │   │   ├── value_objects.py    # SessionToken, TokenHash, GoogleSub
│       │   │   └── ports.py            # UserRepository, SessionRepository,
│       │   │                           # IdentityProvider  (Protocol)
│       │   ├── application/use_cases.py    # SignInWithGoogle, ResolveSession, SignOut
│       │   ├── infrastructure/
│       │   │   ├── repositories.py     # SQLAlchemy
│       │   │   └── google_provider.py  # ACL: đổi code, đọc id_token
│       │   └── interface/
│       │       ├── router.py
│       │       ├── schemas.py          # Pydantic
│       │       └── deps.py             # current_user_id
│       ├── vocabulary/     domain|application|infrastructure|interface
│       ├── srs/            (+ domain/scheduler.py — SM-2)
│       ├── quiz/           (+ infrastructure/srs_read_model.py — ACL sang srs)
│       ├── translation/    (+ domain/cache_key.py, infrastructure/gemini/)
│       └── quota/
├── prompts/
├── tests/
│   ├── conftest.py                     # pgserver + migration + seed
│   ├── test_architecture.py            # <<< luật tầng, mục 3
│   ├── unit/                           # domain thuần — CHẠY KHÔNG CẦN POSTGRES
│   │   ├── test_email.py  test_cache_key.py  test_session.py
│   │   ├── test_srs_card.py  test_language_detector.py  test_quiz_item.py
│   └── integration/
│       ├── test_multi_user_isolation.py    # <<< chốt chặn quan trọng nhất
│       ├── test_quiz_srs_isolation.py
│       └── ...
├── pyproject.toml
└── vercel.json
```

## 7. Lợi ích cụ thể ở dự án này, không phải lợi ích trên lý thuyết

**Phần lớn logic test được không cần Postgres.** SM-2, ghép khoá cache, luật tái dùng đề,
vòng đời phiên, chuẩn hoá email — tất cả thành unit test thuần, chạy mili giây. Quan trọng
với hoàn cảnh hiện tại: những gì tôi *không* kiểm chứng được là hành vi Vercel/Supabase, nên
đẩy càng nhiều logic vào phần kiểm chứng được thì rủi ro bàn giao càng thấp.

**`ports.py` làm ràng buộc #13 thành hình dạng của hệ kiểu.** Repository interface viết bằng
ngôn ngữ nghiệp vụ — `find_owned(user_id, entry_id)` — chứ không phải `find_by_id`. Không
tồn tại method "tìm không cần user", nên không có gì để quên.

**Đổi hạ tầng không đụng nghiệp vụ.** Nếu sau này bỏ Supabase, hoặc thay Gemini bằng mô hình
khác, phần thay đổi nằm gọn trong `infrastructure/`.

## 8. Rủi ro lớn nhất, nói trước

**DDD nửa vời tệ hơn không DDD.** Thư mục tên `domain/` mà bên trong là entity SQLAlchemy,
use case chỉ gọi thẳng repository không có logic nào — trông như kiến trúc nhưng chỉ là
thêm ba lớp gõ phím. `test_architecture.py` ở mục 3 là hàng rào chống chuyện đó, và nó phải
được viết **ở commit đầu tiên**, không phải để sau.

**Mất tính exhaustive của compiler.** Java bắt được lúc biên dịch khi thêm `ErrorCode` mới —
đúng cơ chế đã bắt lỗi cho tôi sáng nay. Bù bằng `mypy --strict` + `assert_never()` ở mọi
chỗ rẽ theo enum. Là bù, không phải tương đương.

## 9. Nếu bạn muốn nhẹ hơn

Bỏ tầng `application/`, cho router gọi thẳng domain + repository. Mất khoảng 20% số file,
đổi lại logic điều phối rơi vào router. Với dự án một người thì đây là đánh đổi hợp lý — tôi
để tầng đó vì bạn nói muốn DDD, không phải vì dự án này bắt buộc có nó.
