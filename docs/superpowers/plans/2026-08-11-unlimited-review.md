# Bỏ giới hạn "một ngày một lần" ở ôn tập — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho phép ôn thêm không giới hạn mà không phá lịch SM-2 — thêm chế độ "Luyện thêm" tách hẳn khỏi lượt ôn theo lịch, cho thẻ vừa quên hiện lại trong buổi, và cho phép tắt hạn mức từ mới mỗi ngày.

**Architecture:** Thêm cột `mode` vào `review_log` (`V8`) để phân biệt `SCHEDULED` với `PRACTICE`, cộng hai endpoint `/api/srs/practice` tách hẳn khỏi `/api/srs/review`. Hàm `practice()` ghi log nhưng **không chạm** `srs_card`. Việc "thẻ vừa quên hiện lại" làm bằng hàng đợi cục bộ trong panel, không đổi schema.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 sync + Postgres 16 (backend); React 18 + TypeScript 5.7 + Vitest + RTL (extension).

**Spec:** [`docs/superpowers/specs/2026-08-11-unlimited-review-design.md`](../specs/2026-08-11-unlimited-review-design.md)

## Global Constraints

- **Ngôn ngữ:** comment, docstring, message lỗi, text hiển thị viết **tiếng Việt đủ dấu**. **Tên class/biến/hàm/tham số/module giữ tiếng Anh.** Lưu UTF-8.
- **Không thêm dependency** (ràng buộc #12).
- **`srs/scheduler.py` KHÔNG được sửa một dòng nào.** Sàn interval 1 ngày và `AGAIN → 1` là đúng và phải giữ.
- **Side panel / Options / content script KHÔNG gọi HTTP** (ràng buộc #1). Mọi request qua `background/api-client.ts`.
- **Hợp đồng message ở `shared/messages.ts`** (ràng buộc #2): interface request → union `ExtensionRequest` → `ResponseMap` → xử lý ở service worker.
- **`shared/types.ts` là bản gương của DTO backend** (ràng buộc #3): khai `T | null`, không dùng optional `?`.
- **Migration append-only** (ràng buộc #8): không sửa `V1`–`V7`; thêm `V8`, và cập nhật model SQLAlchemy trong cùng thay đổi.
- **Mọi truy vấn chạm dữ liệu học phải lọc `vocab_entry.user_id`** (ràng buộc #13). Hai endpoint mới phải có mặt trong `tests/test_multi_user_isolation.py`.
- **Không thêm mã lỗi mới** vào `common/errors.py`.
- File test backend phải tên `test_*.py` trong `tests/` — sai tên là bị bỏ qua **im lặng**.
- **Cổng nghiệm thu:** `uv run pytest` + `uv run mypy app` + `uv run ruff check .` (cwd `api-service/`); `npm test` + `npm run build` (cwd `extension/`).

## Đã kiểm bằng code chạy thật trước khi viết plan

Bốn giả định dưới đây **đã chạy** trên Postgres thật của bộ test, không phải suy luận:

| Giả định | Kết quả thật |
|---|---|
| `ALTER TABLE review_log ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'SCHEDULED'` | Chạy được; dòng cũ nhận `SCHEDULED` |
| `count(*) FILTER (WHERE mode = …)` hai cột trong cùng `GROUP BY` kèm `AT TIME ZONE` | Trả `(2026-08-08, 0, 1)` và `(2026-08-11, 1, 1)` |
| **Bẫy §7.1:** ngày chỉ có `PRACTICE` có lọt vào `GROUP BY` không | **CÓ** — `(2026-08-08, 0, 1)` xuất hiện. Xác nhận bẫy là thật |
| `func.random()` trong `order_by` của SQLAlchemy | Chạy được |

Cách trả 204 của dự án là `-> Response` trả `Response(status_code=204)` (xem `vocabulary/router.py:65-68`), **không** dùng `-> None`.

## File Structure

**Backend — `api-service/`**

| File | Trách nhiệm |
|---|---|
| `migrations/V8__review_log_mode.sql` | **mới** — một cột |
| `app/srs/models.py` | sửa — `ReviewMode`, cột `ReviewLog.mode`, DTO `PracticeRequest` |
| `app/srs/repository.py` | sửa — `find_practice_cards`; `insert_review_log` nhận `mode`; `count_introduced_since` lọc mode |
| `app/srs/service.py` | sửa — `practice()`, `practice_queue()`, `_new_room()` |
| `app/srs/router.py` | sửa — hai route `/practice` |
| `app/stats/repository.py` | sửa — gom theo ngày trả thêm cột `PRACTICE`; hai câu kia lọc `SCHEDULED` |
| `app/stats/models.py` | sửa — `DailyPoint.practice` |
| `app/stats/service.py` | sửa — **bẫy §7.1**: streak và `activeDays` lọc `scheduled > 0` |

**Extension — `extension/src/`**

| File | Trách nhiệm |
|---|---|
| `shared/types.ts` | sửa — `DailyPoint.practice` |
| `shared/messages.ts` | sửa — `GET_PRACTICE_CARDS`, `SUBMIT_PRACTICE` |
| `background/api-client.ts` | sửa — `getPracticeCards`, `submitPractice` |
| `background/service-worker.ts` | sửa — hai nhánh |
| `sidepanel/ReviewTab.tsx` | sửa — chế độ + hàng đợi học lại |
| `sidepanel/StatsCharts.tsx` | sửa — cộng hai số, tách trong `title` |
| `options/Options.tsx` | sửa — nhãn "0 = không giới hạn" |

## Thứ tự và phụ thuộc

```
Task 1 (V8 + mode) → Task 2 (practice API) → Task 3 (isolation)
                  ↘ Task 4 (hạn mức từ mới)
                  ↘ Task 5 (stats + bẫy §7.1) → Task 8 (StatsCharts)
Task 2 ─────────────→ Task 6 (nối dây ext) → Task 7 (ReviewTab)
```

Task 1 phải xong trước mọi thứ — nó đổi chữ ký `insert_review_log`.

---

## Task 1: `V8` + enum `ReviewMode` + `insert_review_log` nhận `mode`

**Files:**
- Create: `api-service/migrations/V8__review_log_mode.sql`
- Modify: `api-service/app/srs/models.py`
- Modify: `api-service/app/srs/repository.py` (hàm `insert_review_log`, quanh dòng 145)
- Modify: `api-service/app/srs/service.py` (chỗ gọi `insert_review_log` trong `review()`)
- Test: `api-service/tests/test_srs_migration.py`

**Interfaces:**
- Consumes: không gì
- Produces: `ReviewMode` (StrEnum: `SCHEDULED`, `PRACTICE`); `ReviewLog.mode: Mapped[str]`; chữ ký mới `insert_review_log(db, card_id, rating, prev_interval, new_interval, mode: ReviewMode) -> None`

- [ ] **Step 1: Viết test đỏ**

Thêm vào cuối `api-service/tests/test_srs_migration.py`:

```python
def test_v8_them_cot_mode_va_backfill_dong_cu(db: Session, owner: NguoiDungTest) -> None:
    """`DEFAULT 'SCHEDULED'` không phải cho tiện: mọi dòng `review_log` đang có ĐỀU đúng là
    lượt ôn theo lịch, nên default đó backfill chính xác toàn bộ lịch sử mà không cần câu
    `UPDATE` nào. Sai chỗ này là thống kê cũ đổi số."""
    kieu, mac_dinh, cho_null = db.execute(
        text(
            "SELECT data_type, column_default, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'review_log' AND column_name = 'mode'"
        )
    ).one()

    assert kieu == "character varying"
    assert "SCHEDULED" in mac_dinh
    assert cho_null == "NO"


def test_v8_dong_review_log_khong_ghi_mode_nhan_scheduled(
    db: Session, owner: NguoiDungTest
) -> None:
    """Chèn thẳng bằng SQL không nêu `mode` — mô phỏng đúng dòng có từ trước V8."""
    vocab_id = _tu(db, owner.id, "mitigate")
    card_id = _the(db, vocab_id)
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval) "
            "VALUES (:c, 'GOOD', 1, 6)"
        ),
        {"c": card_id},
    )
    db.commit()

    mode = db.execute(
        text("SELECT mode FROM review_log WHERE card_id = :c"), {"c": card_id}
    ).scalar_one()
    assert mode == "SCHEDULED"
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd api-service && uv run pytest tests/test_srs_migration.py -v -k v8
```

Kỳ vọng: FAIL — `information_schema` không có cột `mode`, câu `.one()` ném `NoResultFound`.

- [ ] **Step 3a: Viết migration**

Tạo `api-service/migrations/V8__review_log_mode.sql`:

```sql
-- Phân biệt lượt ôn theo lịch với lượt luyện thêm.
--
-- `DEFAULT 'SCHEDULED'` là phần quan trọng nhất của migration này: mọi dòng đang có đều
-- đúng là lượt ôn theo lịch, nên default backfill chính xác toàn bộ lịch sử mà không cần
-- câu UPDATE nào, và không con số nào ở tab Thống kê đổi.
--
-- Migration KHÔNG chạy lúc cold start trên Vercel (nhiều instance cùng ALTER TABLE là công
-- thức khoá lẫn nhau) — trên Supabase phải chạy tay một lần.
ALTER TABLE review_log ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'SCHEDULED';
```

- [ ] **Step 3b: Thêm enum và cột vào `app/srs/models.py`**

Thêm enum cạnh `Rating`:

```python
class ReviewMode(enum.StrEnum):
    """Phân biệt hai loại lượt ôn. Ghi nhầm loại KHÔNG làm gì đỏ — nó chỉ lặng lẽ làm sai
    streak và tỉ lệ nhớ ở tab Thống kê, hoặc phá lịch SM-2."""

    #: Lượt ôn theo lịch — ĐỔI due_date, interval_days, ease_factor, repetitions.
    SCHEDULED = "SCHEDULED"
    #: Luyện thêm — KHÔNG đụng gì tới lịch.
    PRACTICE = "PRACTICE"
```

Thêm cột vào `ReviewLog`, ngay sau `new_interval`:

```python
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
```

Không đặt `default=` ở tầng model: `insert_review_log` bắt buộc truyền `mode`, nên không có đường nào ghi thiếu.

Thêm DTO cạnh `ReviewRequest`:

```python
class PracticeRequest(ApiModel):
    """Cùng hình dạng `ReviewRequest` nhưng là kiểu RIÊNG, không tái dùng.

    Hai request đi vào hai endpoint có hậu quả khác hẳn nhau — một cái đổi lịch, một cái
    không. Dùng chung một kiểu làm chỗ khác biệt đó biến mất khỏi chữ ký hàm."""

    card_id: int
    rating: Rating
```

- [ ] **Step 3c: `insert_review_log` nhận `mode` bắt buộc**

Sửa `api-service/app/srs/repository.py`:

```python
def insert_review_log(
    db: Session,
    card_id: int,
    rating: Rating,
    prev_interval: int,
    new_interval: int,
    mode: ReviewMode,
) -> None:
    """`mode` BẮT BUỘC, cố ý không có giá trị mặc định.

    Đặt default `SCHEDULED` cho tiện nghĩa là mọi người gọi sau này mặc nhiên ghi lượt ôn
    theo lịch mà không hề chọn — và ghi nhầm loại ở đây không làm gì đỏ. Bắt buộc thì mypy
    ép từng chỗ gọi phải quyết định.
    """
    db.add(
        ReviewLog(
            card_id=card_id,
            rating=rating.value,
            prev_interval=prev_interval,
            new_interval=new_interval,
            mode=mode.value,
        )
    )
    db.flush()
```

Thêm `ReviewMode` vào khối import từ `app.srs.models`.

- [ ] **Step 3d: Cập nhật chỗ gọi trong `service.review()`**

Trong `api-service/app/srs/service.py`, hàm `review()`:

```python
    repo.insert_review_log(
        db,
        card_id=card.id,
        rating=rating,
        prev_interval=prev_interval,
        new_interval=nxt.interval_days,
        mode=ReviewMode.SCHEDULED,
    )
```

Thêm `ReviewMode` vào khối import từ `app.srs.models`.

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd api-service && uv run pytest && uv run mypy app && uv run ruff check .
```

Kỳ vọng: tất cả xanh. Toàn bộ suite phải xanh — nếu test cũ đỏ vì thiếu `mode`, đó là chỗ gọi `insert_review_log` bị bỏ sót, sửa chỗ gọi chứ đừng thêm default.

- [ ] **Step 5: Commit**

```bash
git add api-service/migrations/V8__review_log_mode.sql api-service/app/srs/models.py \
        api-service/app/srs/repository.py api-service/app/srs/service.py \
        api-service/tests/test_srs_migration.py
git commit -m "feat(srs): cột mode phân biệt lượt ôn theo lịch với luyện thêm"
```

---

## Task 2: Hàng đợi luyện thêm và hai endpoint `/api/srs/practice`

**Files:**
- Modify: `api-service/app/srs/repository.py` (thêm `find_practice_cards`)
- Modify: `api-service/app/srs/service.py` (thêm `practice_queue`, `practice`)
- Modify: `api-service/app/srs/router.py`
- Test: `api-service/tests/test_srs_practice.py` (**mới**)

**Interfaces:**
- Consumes: `ReviewMode`, `PracticeRequest`, `insert_review_log(..., mode)` (Task 1); `repo.find_owned_card(db, card_id, user_id) -> SrsCard | None`, `_load_fresh_distractors`, `_request_missing`, `_to_dto` (đã có trong `srs/service.py`)
- Produces: `GET /api/srs/practice?limit=N → list[CardDto]`; `POST /api/srs/practice {cardId, rating} → 204`

- [ ] **Step 1: Viết test đỏ**

Tạo `api-service/tests/test_srs_practice.py`:

```python
"""Chế độ luyện thêm — bất biến trung tâm là `srs_card` KHÔNG ĐỔI.

Mọi thứ khác trong tính năng này hỏng thì còn sửa được; một cột trong `srs_card` bị đổi sai
là lịch học của người dùng hỏng vĩnh viễn và không khôi phục được.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import NguoiDungTest


def _seed_the(
    db: Session, user_id: int, term: str, repetitions: int = 2, interval_days: int = 6
) -> int:
    """Một từ kèm thẻ SRS. Trả `srs_card.id`. `repetitions = 0` cho thẻ NEW."""
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id) "
                "VALUES (:t, :t, 'en', 'verb', 'nghĩa', :u) RETURNING id"
            ),
            {"t": term, "u": user_id},
        ).scalar_one()
    )
    state = "NEW" if repetitions == 0 else "REVIEW"
    card_id = int(
        db.execute(
            text(
                "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, "
                "interval_days, ease_factor) "
                "VALUES (:v, CURRENT_DATE + 5, :s, :r, :i, 2.5) RETURNING id"
            ),
            {"v": vocab_id, "s": state, "r": repetitions, "i": interval_days},
        ).scalar_one()
    )
    db.commit()
    return card_id


def _chup_the(db: Session, card_id: int) -> tuple[Any, ...]:
    db.expire_all()
    return tuple(
        db.execute(
            text(
                "SELECT due_date::text, interval_days, ease_factor, repetitions, lapses, state "
                "FROM srs_card WHERE id = :c"
            ),
            {"c": card_id},
        ).one()
    )


def test_luyen_nam_lan_khong_doi_mot_cot_nao_cua_the(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Bất biến trung tâm của cả spec.

    Năm lượt chứ không một: nếu ai đó vô ý gọi `next_schedule` trong `practice()`, một lượt
    có thể trùng giá trị cũ do làm tròn, năm lượt thì không."""
    card_id = _seed_the(db, owner.id, "mitigate")
    truoc = _chup_the(db, card_id)

    for rating in ("AGAIN", "HARD", "GOOD", "EASY", "GOOD"):
        resp = client.post(
            "/api/srs/practice",
            headers=owner.headers,
            json={"cardId": card_id, "rating": rating},
        )
        assert resp.status_code == 204

    assert _chup_the(db, card_id) == truoc


def test_luyen_ghi_dung_mot_dong_mode_practice(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    card_id = _seed_the(db, owner.id, "mitigate", interval_days=6)

    client.post(
        "/api/srs/practice", headers=owner.headers, json={"cardId": card_id, "rating": "GOOD"}
    )

    mode, prev, moi = db.execute(
        text("SELECT mode, prev_interval, new_interval FROM review_log WHERE card_id = :c"),
        {"c": card_id},
    ).one()
    assert mode == "PRACTICE"
    # Không phải số giả: lịch thật sự không đổi nên hai con số thật sự bằng nhau.
    assert (prev, moi) == (6, 6)


def test_hang_luyen_loai_the_new(client: Any, db: Session, owner: NguoiDungTest) -> None:
    """Lượt đầu đời của một thẻ phải đi đường có lịch, nếu không nó mắc kẹt ở NEW vĩnh viễn."""
    _seed_the(db, owner.id, "mitigate", repetitions=2)
    _seed_the(db, owner.id, "brandnew", repetitions=0, interval_days=0)

    ra = client.get("/api/srs/practice", headers=owner.headers)

    assert ra.status_code == 200
    assert [c["term"] for c in ra.json()] == ["mitigate"]


def test_hang_luyen_van_chua_the_dang_den_han(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Cố ý: luật "mọi từ đã học" giải thích được bằng một câu, và luyện một thẻ đang đến hạn
    không làm nó biến mất khỏi hàng ôn thật."""
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id) "
                "VALUES ('due','due','en','verb','đến hạn',:u) RETURNING id"
            ),
            {"u": owner.id},
        ).scalar_one()
    )
    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, interval_days) "
            "VALUES (:v, CURRENT_DATE, 'REVIEW', 3, 1)"
        ),
        {"v": vocab_id},
    )
    db.commit()

    assert [c["term"] for c in client.get("/api/srs/practice", headers=owner.headers).json()] == [
        "due"
    ]


def test_luyen_the_khong_ton_tai_tra_404(client: Any, owner: NguoiDungTest) -> None:
    resp = client.post(
        "/api/srs/practice", headers=owner.headers, json={"cardId": 999999, "rating": "GOOD"}
    )
    assert resp.status_code == 404


def test_chua_dang_nhap_tra_401(client: Any) -> None:
    assert client.get("/api/srs/practice").status_code == 401
    assert client.post("/api/srs/practice", json={"cardId": 1, "rating": "GOOD"}).status_code == 401
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd api-service && uv run pytest tests/test_srs_practice.py -v
```

Kỳ vọng: FAIL — route `/api/srs/practice` chưa tồn tại, mọi ca trả 404 (và ca 404 sẵn có thì xanh giả; đừng để nó đánh lừa).

- [ ] **Step 3a: `find_practice_cards` trong `repository.py`**

```python
def find_practice_cards(
    db: Session, user_id: int, limit: int
) -> list[tuple[SrsCard, VocabEntry]]:
    """Hàng luyện thêm: mọi từ đã học ít nhất một lượt, xáo ngẫu nhiên.

    `repetitions >= 1` loại thẻ NEW — lượt đầu đời của một thẻ phải đi đường có lịch, nếu
    không nó mắc kẹt ở trạng thái NEW vĩnh viễn.

    KHÔNG loại thẻ đang đến hạn. Luật "mọi từ đã học" giải thích được bằng một câu, còn "mọi
    từ đã học trừ những từ đến hạn hôm nay" thì không — và luyện một thẻ đang đến hạn không
    làm nó biến mất khỏi hàng ôn thật, đúng như nó phải thế.
    """
    stmt = (
        select(SrsCard, VocabEntry)
        .join(VocabEntry, SrsCard.vocab_entry_id == VocabEntry.id)
        .where(VocabEntry.user_id == user_id, SrsCard.repetitions >= 1)
        .order_by(func.random())
        .limit(limit)
    )
    return [(row[0], row[1]) for row in db.execute(stmt).all()]
```

- [ ] **Step 3b: `practice_queue` và `practice` trong `service.py`**

```python
def practice_queue(
    db: Session, user_id: int, limit: int, tasks: BackgroundTasks
) -> list[CardDto]:
    """Xấp thẻ luyện thêm. Dùng lại đúng đường bù mồi nhử của `due()` — bỏ qua sẽ làm chế độ
    luyện im lặng không dùng được với từ chưa sinh mồi."""
    queue = repo.find_practice_cards(db, user_id, limit)
    by_vocab_id = _load_fresh_distractors(db, queue)
    _request_missing(tasks, db, queue, by_vocab_id)
    return [_to_dto(card, entry, by_vocab_id) for card, entry in queue]


def practice(db: Session, user_id: int, card_id: int, rating: Rating) -> None:
    """Ghi một lượt luyện thêm. KHÔNG đụng lịch.

    Điều quan trọng nhất của hàm này là thứ nó KHÔNG làm: không gọi `next_schedule`, không
    gán lại `card.*`. Đó là toàn bộ điểm khác biệt với `review()`. Thêm một dòng chạm `card`
    ở đây là làm hỏng đúng thứ chế độ luyện thêm sinh ra để bảo vệ — ôn một thẻ 5 lần trong
    ngày sẽ đẩy interval 1 → 6 → 15 → 37 → 92 ngày.
    """
    card = repo.find_owned_card(db, card_id, user_id)
    if card is None:
        raise AppError.of(ErrorCode.NOT_FOUND, f"Không tìm thấy thẻ id={card_id}")

    repo.insert_review_log(
        db,
        card_id=card.id,
        rating=rating,
        # Không phải số giả: lịch thật sự không đổi nên hai con số thật sự bằng nhau.
        prev_interval=card.interval_days,
        new_interval=card.interval_days,
        mode=ReviewMode.PRACTICE,
    )
```

- [ ] **Step 3c: Hai route trong `router.py`**

Thêm `Response` vào import từ `fastapi`, và `PracticeRequest` vào import từ `app.srs.models`:

```python
@router.get("/practice", response_model=list[CardDto])
def practice_queue(
    user_id: CurrentUserId,
    db: Db,
    tasks: BackgroundTasks,
    limit: int = 50,
) -> list[CardDto]:
    """Xấp thẻ luyện thêm — mọi từ đã học, xáo ngẫu nhiên. Không có khái niệm "đến hạn" ở
    đây, nên cũng không có tham số `newLimit`."""
    return service.practice_queue(db, user_id, _clamp(limit, MAX_LIMIT), tasks)


@router.post("/practice", status_code=204)
def submit_practice(request: PracticeRequest, user_id: CurrentUserId, db: Db) -> Response:
    """Tách hẳn khỏi `POST /review` chứ không thêm field `mode` vào đó.

    `ReviewResponse` mang `nextDueDate`, `intervalDays`, `easeFactor` — luyện thêm không có
    ba thứ đó, nên gộp chung buộc phải trả số giả cho nửa số lượt gọi. Và nhầm mode là hỏng
    im lặng: gửi PRACTICE cho một lượt ôn thật thì lịch đứng yên mãi mãi.
    """
    service.practice(db, user_id, request.card_id, request.rating)
    return Response(status_code=204)
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd api-service && uv run pytest tests/test_srs_practice.py -v && uv run pytest && uv run mypy app && uv run ruff check .
```

Kỳ vọng: 6 ca mới xanh, toàn suite xanh, mypy và ruff sạch.

- [ ] **Step 5: Chứng minh test bất biến trung tâm bắt được lỗi**

Tạm thêm vào `practice()`, ngay trước `insert_review_log`:

```python
    card.repetitions += 1
```

Chạy `uv run pytest tests/test_srs_practice.py -k khong_doi_mot_cot -v` — phải **ĐỎ**. Rồi **xoá dòng vừa thêm**, chạy lại cho xanh, và xác nhận `git diff api-service/app/srs/service.py` không còn dòng đó.

Dán cả output đỏ lẫn xanh vào báo cáo. Một test không bao giờ đỏ là một test không bảo vệ gì.

- [ ] **Step 6: Commit**

```bash
git add api-service/app/srs/repository.py api-service/app/srs/service.py \
        api-service/app/srs/router.py api-service/tests/test_srs_practice.py
git commit -m "feat(srs): hai endpoint luyện thêm, không đụng lịch SM-2"
```

---

## Task 3: Chốt chặn cách ly người dùng cho `/api/srs/practice`

Task riêng vì đây là **cổng an toàn của ràng buộc #13**, không phải phần phụ của Task 2.

**Files:**
- Modify: `api-service/tests/test_multi_user_isolation.py` (thêm vào section `srs`)

**Interfaces:**
- Consumes: hai endpoint `/api/srs/practice` (Task 2); fixture `hai_nguoi`, helper `_the_cua` sẵn có trong chính file đó
- Produces: không gì

- [ ] **Step 1: Viết test**

Thêm vào `api-service/tests/test_multi_user_isolation.py`, trong section `srs`:

```python
def test_hang_luyen_chi_chua_the_cua_minh(client: Any, hai_nguoi: HaiNguoi) -> None:
    ra = client.get("/api/srs/practice", headers=hai_nguoi.a.headers)
    assert ra.status_code == 200
    assert [c["meaningVi"] for c in ra.json()] == ["giảm nhẹ (của A)"]

    rb = client.get("/api/srs/practice", headers=hai_nguoi.b.headers)
    assert rb.status_code == 200
    assert [c["meaningVi"] for c in rb.json()] == ["giảm nhẹ (của B)"]


def test_luyen_the_cua_nguoi_khac_tra_404_va_khong_ghi_log(
    client: Any, db: Session, hai_nguoi: HaiNguoi
) -> None:
    """Kiểm cả status LẪN dữ liệu: trả 404 mà vẫn ghi log là ca tệ nhất và im lặng nhất —
    số liệu thống kê của A sẽ nhích lên vì một thao tác đã bị từ chối."""
    the_b = _the_cua(db, hai_nguoi.vocab_b)

    resp = client.post(
        "/api/srs/practice",
        headers=hai_nguoi.a.headers,
        json={"cardId": the_b, "rating": "GOOD"},
    )
    assert resp.status_code == 404

    con_lai = db.execute(
        text("SELECT count(*) FROM review_log WHERE card_id = :c"), {"c": the_b}
    ).scalar_one()
    assert con_lai == 0
```

- [ ] **Step 2: Chạy test — kỳ vọng XANH ngay lần đầu**

```bash
cd api-service && uv run pytest tests/test_multi_user_isolation.py -v
```

Test này là chốt hồi quy, không phải đặc tả hành vi mới — Task 2 đã lọc `user_id` đúng rồi.

- [ ] **Step 3: Chứng minh nó bắt được lỗi**

Tạm bỏ `VocabEntry.user_id == user_id` khỏi `find_practice_cards`, chạy:

```bash
cd api-service && uv run pytest tests/test_multi_user_isolation.py -k hang_luyen -v
```

Kỳ vọng: **ĐỎ**. Khôi phục, chạy lại cho xanh, xác nhận `git diff api-service/app/srs/repository.py` rỗng.

- [ ] **Step 4: Commit**

```bash
git add api-service/tests/test_multi_user_isolation.py
git commit -m "test(srs): chốt chặn cách ly người dùng cho /api/srs/practice"
```

---

## Task 4: Hạn mức từ mới — `0` nghĩa là không giới hạn

**Files:**
- Modify: `api-service/app/srs/service.py` (thay `_remaining_new_today` bằng `_new_room`; sửa `due()` và `stats()`)
- Modify: `api-service/app/srs/repository.py` (`count_introduced_since` lọc mode)
- Test: `api-service/tests/test_srs_service.py`

**Interfaces:**
- Consumes: `ReviewMode` (Task 1)
- Produces: `_new_room(db, user_id, new_limit, cap) -> int` — nội bộ `srs/service.py`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `api-service/tests/test_srs_service.py`:

```python
def test_new_limit_bang_0_la_khong_gioi_han(client: Any, db: Session, owner: NguoiDungTest) -> None:
    """`0` là cách người dùng tắt hẳn hạn mức từ ô "Từ mới mỗi ngày" ở Options.

    Trước thay đổi này, `0` nghĩa là "không được học từ mới nào" — đúng nghĩa đen nhưng vô
    dụng, vì không ai đặt hạn mức 0 để tự cấm mình học."""
    for i in range(7):
        _seed_the_new(db, owner.id, f"word{i}")

    ra = client.get("/api/srs/due?limit=50&newLimit=0", headers=owner.headers)

    assert ra.status_code == 200
    assert len(ra.json()) == 7


def test_new_limit_duong_van_chan_dung(client: Any, db: Session, owner: NguoiDungTest) -> None:
    for i in range(7):
        _seed_the_new(db, owner.id, f"word{i}")

    ra = client.get("/api/srs/due?limit=50&newLimit=3", headers=owner.headers)

    assert len(ra.json()) == 3


def test_luot_practice_khong_tinh_vao_han_muc_tu_moi(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`count_introduced_since` nhận diện lượt đầu đời bằng `prev_interval == 0`. Dòng
    PRACTICE không được lọt vào phép đếm đó, nếu không luyện thêm sẽ ăn mất hạn mức từ mới
    của ngày hôm sau."""
    card_id = _seed_the_hoc_roi(db, owner.id, "mitigate")
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode) "
            "VALUES (:c, 'GOOD', 0, 0, 'PRACTICE')"
        ),
        {"c": card_id},
    )
    db.commit()
    for i in range(3):
        _seed_the_new(db, owner.id, f"word{i}")

    ra = client.get("/api/srs/due?limit=50&newLimit=3", headers=owner.headers)

    # 3 thẻ mới + 1 thẻ đã học nếu nó đến hạn; điều đang kiểm là hạn mức từ mới KHÔNG bị
    # dòng PRACTICE ăn mất, tức vẫn đủ 3 thẻ NEW.
    assert sum(1 for c in ra.json() if c["state"] == "NEW") == 3
```

Thêm hai helper ở đầu file nếu chưa có (đọc file trước — nếu đã có helper tương đương thì dùng lại, đừng dựng cái thứ hai):

```python
def _seed_the_new(db: Session, user_id: int, term: str) -> int:
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id) "
                "VALUES (:t, :t, 'en', 'verb', 'nghĩa', :u) RETURNING id"
            ),
            {"t": term, "u": user_id},
        ).scalar_one()
    )
    card_id = int(
        db.execute(
            text(
                "INSERT INTO srs_card (vocab_entry_id, due_date, state) "
                "VALUES (:v, CURRENT_DATE, 'NEW') RETURNING id"
            ),
            {"v": vocab_id},
        ).scalar_one()
    )
    db.commit()
    return card_id


def _seed_the_hoc_roi(db: Session, user_id: int, term: str) -> int:
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id) "
                "VALUES (:t, :t, 'en', 'verb', 'nghĩa', :u) RETURNING id"
            ),
            {"t": term, "u": user_id},
        ).scalar_one()
    )
    card_id = int(
        db.execute(
            text(
                "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, "
                "interval_days) VALUES (:v, CURRENT_DATE, 'REVIEW', 2, 6) RETURNING id"
            ),
            {"v": vocab_id},
        ).scalar_one()
    )
    db.commit()
    return card_id
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd api-service && uv run pytest tests/test_srs_service.py -v -k "new_limit or practice_khong_tinh"
```

Kỳ vọng: `test_new_limit_bang_0_la_khong_gioi_han` FAIL với `assert 0 == 7`.

- [ ] **Step 3a: Thay `_remaining_new_today` bằng `_new_room`**

Trong `api-service/app/srs/service.py`, xoá `_remaining_new_today` và thêm:

```python
def _introduced_today(db: Session, user_id: int) -> int:
    """Số thẻ MỚI đã được đưa vào học kể từ nửa đêm hôm nay.

    Mốc nửa đêm tính theo giờ HỆ THỐNG (`astimezone()` gắn offset local vào) — cùng lý do
    biến TZ được truyền vào container: ngày phải đổi lúc nửa đêm giờ Việt Nam. Gửi một mốc
    thời gian KHÔNG có offset xuống Postgres thì nó tự diễn giải theo timezone của session,
    lệch mất vài giờ mà không có gì báo.
    """
    start_of_day = datetime.combine(date.today(), time.min).astimezone()
    return repo.count_introduced_since(db, user_id, start_of_day)


def _new_room(db: Session, user_id: int, new_limit: int, cap: int) -> int:
    """Số thẻ MỚI còn được nhận hôm nay, đã kẹp trong `cap`.

    `new_limit = 0` nghĩa là KHÔNG giới hạn — đó là cách người dùng tắt hẳn hạn mức từ ô
    "Từ mới mỗi ngày" ở Options. Trước đây `0` nghĩa đen là "cấm học từ mới", một hành vi
    không ai muốn và không ai dùng.

    Gom hai chỗ tính vào một hàm để luật "0 là không giới hạn" chỉ tồn tại ở đúng một chỗ;
    `due()` và `stats()` trước đây tự ghép `min()` theo hai cách hơi khác nhau.
    """
    if new_limit <= 0:
        return max(0, cap)
    return max(0, min(cap, new_limit - _introduced_today(db, user_id)))
```

Trong `due()`, thay:

```python
    room = _new_room(db, user_id, new_limit, limit - len(queue))
    if room > 0:
        queue = queue + repo.find_new_cards(db, user_id, room)
```

Trong `stats()`, thay:

```python
    new_allowed = _new_room(db, user_id, new_limit, new_total)
```

- [ ] **Step 3b: `count_introduced_since` lọc `mode = 'SCHEDULED'`**

Trong `api-service/app/srs/repository.py`, thêm một điều kiện vào `.where(...)`:

```python
            ReviewLog.mode == ReviewMode.SCHEDULED.value,
```

Và bổ sung vào docstring của hàm:

```
    Lọc `mode = SCHEDULED` là bắt buộc: hàng luyện chỉ chứa thẻ `repetitions >= 1` nên hôm
    nay không dòng PRACTICE nào có `prev_interval = 0` — nhưng bất biến đó phụ thuộc vào
    định nghĩa hàng luyện, thứ có thể đổi. Một mệnh đề WHERE làm nó không phụ thuộc nữa.
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd api-service && uv run pytest && uv run mypy app && uv run ruff check .
```

- [ ] **Step 5: Commit**

```bash
git add api-service/app/srs/service.py api-service/app/srs/repository.py \
        api-service/tests/test_srs_service.py
git commit -m "feat(srs): newLimit = 0 nghĩa là không giới hạn từ mới"
```

---

## Task 5: Thống kê — `daily.practice`, và bịt bẫy §7.1

**Đây là task rủi ro nhất của plan.** Đọc kỹ Step 3b.

**Files:**
- Modify: `api-service/app/stats/repository.py`
- Modify: `api-service/app/stats/models.py`
- Modify: `api-service/app/stats/service.py`
- Test: `api-service/tests/test_stats_endpoint.py`, `api-service/tests/test_stats_repository.py`

**Interfaces:**
- Consumes: `ReviewMode` (Task 1)
- Produces: `dem_luot_on_theo_ngay(db, user_id) -> list[tuple[date, int, int]]` — `(ngày, số SCHEDULED, số PRACTICE)`; `DailyPoint` có thêm `practice: int` → JSON `practice`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `api-service/tests/test_stats_endpoint.py`:

```python
def _seed_luot(db: Session, card_id: int, mode: str, so_luot: int) -> None:
    for _ in range(so_luot):
        db.execute(
            text(
                "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode) "
                "VALUES (:c, 'GOOD', 1, 6, :m)"
            ),
            {"c": card_id, "m": mode},
        )


def test_luot_practice_vao_daily_practice_khong_vao_reviews(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    _, card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot(db, card_id, "SCHEDULED", 2)
    _seed_luot(db, card_id, "PRACTICE", 5)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()
    hom_nay = body["daily"][-1]

    assert hom_nay["reviews"] == 2
    assert hom_nay["practice"] == 5


def test_luot_practice_khong_vao_totals_va_recall(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`totals` và `recall` giữ nguyên nghĩa cũ: chỉ đếm lượt ôn theo lịch. Trộn hai loại
    hoạt động vào tỉ lệ nhớ thì con số không so sánh được với chính nó tháng trước."""
    _, card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot(db, card_id, "SCHEDULED", 2)
    _seed_luot(db, card_id, "PRACTICE", 5)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["reviews"] == 2
    assert body["recall"] == {"again": 0, "hard": 0, "good": 2, "easy": 0}


def test_ngay_chi_co_practice_khong_giu_streak_va_khong_tinh_active_day(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """BẪY §7.1 — ca quan trọng nhất của task này.

    `dem_luot_on_theo_ngay` một mình nuôi bốn con số. Thêm cột đếm PRACTICE vào câu đó làm
    GROUP BY bắt đầu trả về cả những ngày CHỈ có lượt luyện; nếu streak và activeDays lấy
    danh sách ngày từ đó, chúng bắt đầu tính cả ngày chỉ luyện — mà không ai chạm vào
    `streak.py`. Đã xác minh bằng SQL thật: ngày chỉ có PRACTICE CÓ lọt vào GROUP BY.
    """
    _, card_id = _seed_the(db, owner.id, "mitigate")
    # Hôm nay: chỉ luyện thêm, không ôn theo lịch.
    _seed_luot(db, card_id, "PRACTICE", 4)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["streak"]["current"] == 0
    assert body["streak"]["lastActiveDate"] is None
    assert body["totals"]["activeDays"] == 0
    assert body["totals"]["reviews"] == 0
    # Nhưng công sức vẫn hiện ở biểu đồ.
    assert body["daily"][-1]["practice"] == 4
```

Và thêm vào `api-service/tests/test_stats_repository.py`:

```python
def test_gom_theo_ngay_tach_hai_loai(db: Session, owner: NguoiDungTest) -> None:
    card_id = _seed_the(db, owner.id, "mitigate")
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode, "
            "reviewed_at) VALUES (:c,'GOOD',1,6,'SCHEDULED','2026-08-10 05:00:00+00')"
        ),
        {"c": card_id},
    )
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode, "
            "reviewed_at) VALUES (:c,'GOOD',6,6,'PRACTICE','2026-08-10 06:00:00+00')"
        ),
        {"c": card_id},
    )
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode, "
            "reviewed_at) VALUES (:c,'GOOD',6,6,'PRACTICE','2026-08-08 05:00:00+00')"
        ),
        {"c": card_id},
    )
    db.commit()

    # Ngày 08/8 CHỈ có lượt luyện — nó VẪN xuất hiện với scheduled = 0. Đó là hành vi đúng
    # của repository; việc loại nó khỏi streak là trách nhiệm của service.
    assert repo.dem_luot_on_theo_ngay(db, owner.id) == [
        (date(2026, 8, 8), 0, 1),
        (date(2026, 8, 10), 1, 1),
    ]
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd api-service && uv run pytest tests/test_stats_endpoint.py tests/test_stats_repository.py -v
```

Kỳ vọng: các ca mới FAIL (`KeyError: 'practice'`, và câu gom trả tuple 2 phần tử thay vì 3).

- [ ] **Step 3a: `stats/repository.py`**

Sửa `dem_luot_on_theo_ngay`:

```python
def dem_luot_on_theo_ngay(db: Session, user_id: int) -> list[tuple[date, int, int]]:
    """`(ngày, số lượt SCHEDULED, số lượt PRACTICE)` trên TOÀN BỘ lịch sử, tăng dần.

    CẢNH BÁO cho người gọi: ngày CHỈ có lượt PRACTICE vẫn nằm trong kết quả, với
    `scheduled = 0`. Đó là hành vi đúng của hàm này — nhưng `streak` và `totals.activeDays`
    PHẢI lọc `scheduled > 0`, nếu không chúng bắt đầu tính cả ngày chỉ luyện thêm. Xem
    docstring của `service.lay_thong_ke`.
    """
    ngay = _ngay_dia_phuong().label("ngay")
    cau = (
        select(
            ngay,
            func.count().filter(ReviewLog.mode == ReviewMode.SCHEDULED.value),
            func.count().filter(ReviewLog.mode == ReviewMode.PRACTICE.value),
        )
        .select_from(ReviewLog)
        .join(SrsCard, SrsCard.id == ReviewLog.card_id)
        .join(VocabEntry, VocabEntry.id == SrsCard.vocab_entry_id)
        .where(VocabEntry.user_id == user_id)
        .group_by(ngay)
        .order_by(ngay)
    )
    return [(hang[0], int(hang[1]), int(hang[2])) for hang in db.execute(cau).all()]
```

Thêm vào `.where(...)` của `dem_luot_on_theo_rating`:

```python
            ReviewLog.mode == ReviewMode.SCHEDULED.value,
```

kèm một dòng docstring giải thích: *"Chỉ đếm lượt theo lịch — tỉ lệ nhớ trộn hai loại hoạt động thì không so sánh được với chính nó tháng trước."*

Thêm `ReviewMode` vào khối import từ `app.srs.models`.

- [ ] **Step 3b: `stats/service.py` — BỊT BẪY §7.1**

```python
def lay_thong_ke(db: Session, user_id: int) -> StatsDto:
    theo_ngay = repo.dem_luot_on_theo_ngay(db, user_id)
    hom_nay = _hom_nay()

    # BẪY: `theo_ngay` chứa CẢ những ngày chỉ có lượt luyện thêm (scheduled = 0). Lấy
    # thẳng danh sách ngày từ đó là cho streak tính cả ngày chỉ luyện — phá đúng quy tắc
    # "streak đo kỷ luật theo lịch", mà không ai chạm vào `streak.py`.
    ngay_co_on_theo_lich = [ngay for ngay, scheduled, _ in theo_ngay if scheduled > 0]
    st = tinh_streak(ngay_co_on_theo_lich, hom_nay)

    scheduled_theo_ngay = {ngay: scheduled for ngay, scheduled, _ in theo_ngay}
    practice_theo_ngay = {ngay: practice for ngay, _, practice in theo_ngay}
    theo_rating = repo.dem_luot_on_theo_rating(db, user_id)
    theo_loai = repo.thong_ke_quiz_theo_loai(db, user_id)

    return StatsDto(
        streak=StreakDto(
            current=st.current, longest=st.longest, last_active_date=st.last_active
        ),
        totals=TotalsDto(
            reviews=sum(scheduled for _, scheduled, _ in theo_ngay),
            learned_words=srs_repo.count_learned(db, user_id),
            # Cùng lý do với streak: chỉ đếm ngày có ôn THEO LỊCH.
            active_days=len(ngay_co_on_theo_lich),
        ),
        daily=[
            DailyPoint(
                date=ngay,
                reviews=scheduled_theo_ngay.get(ngay, 0),
                practice=practice_theo_ngay.get(ngay, 0),
            )
            for ngay in _cua_so(hom_nay)
        ],
        recall=RecallDto(
            again=theo_rating.get("AGAIN", 0),
            hard=theo_rating.get("HARD", 0),
            good=theo_rating.get("GOOD", 0),
            easy=theo_rating.get("EASY", 0),
        ),
        quiz=[_quiz_dto(loai, theo_loai.get(loai.value)) for loai in QuizType],
    )
```

- [ ] **Step 3c: `stats/models.py`**

Thêm vào `DailyPoint`:

```python
    #: Số lượt luyện thêm trong ngày. Field RIÊNG chứ không cộng vào `reviews`: `reviews`
    #: giữ nguyên nghĩa cũ (chỉ lượt theo lịch), nên mọi test thống kê cũ phải xanh nguyên.
    practice: int
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd api-service && uv run pytest && uv run mypy app && uv run ruff check .
```

**Mọi test thống kê cũ phải xanh nguyên.** Nếu một test cũ đỏ, nghĩa là đã đổi nghĩa một field đang có chứ không phải thêm field mới — đó là tín hiệu dừng lại, **không phải test cần sửa**. Báo lại thay vì sửa test.

- [ ] **Step 5: Chứng minh bẫy §7.1 được bịt thật**

Tạm đổi dòng streak trong `service.py` thành:

```python
    ngay_co_on_theo_lich = [ngay for ngay, _, _ in theo_ngay]
```

Chạy `uv run pytest tests/test_stats_endpoint.py -k chi_co_practice -v` — phải **ĐỎ** với `assert 1 == 0`. Khôi phục, chạy lại cho xanh.

Dán cả output đỏ lẫn xanh. Đây là chốt chặn quan trọng nhất của task.

- [ ] **Step 6: Commit**

```bash
git add api-service/app/stats/ api-service/tests/test_stats_endpoint.py \
        api-service/tests/test_stats_repository.py
git commit -m "feat(stats): tách lượt luyện thêm khỏi streak, recall và totals"
```

---

## Task 6: Nối dây phía extension

**Files:**
- Modify: `extension/src/shared/types.ts`
- Modify: `extension/src/shared/messages.ts`
- Modify: `extension/src/background/api-client.ts`
- Modify: `extension/src/background/service-worker.ts`
- Test: `extension/src/background/api-client.test.ts`, `extension/src/background/service-worker.test.ts`

**Interfaces:**
- Consumes: `GET/POST /api/srs/practice` (Task 2); `daily[].practice` (Task 5)
- Produces: `DailyPoint { date: string; reviews: number; practice: number }`; message `GET_PRACTICE_CARDS { type, limit }` → `CardDto[]`; message `SUBMIT_PRACTICE { type, cardId, rating }` → `null`; `getPracticeCards(limit)`, `submitPractice({cardId, rating})`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `extension/src/background/api-client.test.ts`, cạnh ca của `getDueCards`. Dùng `fetchMock`, `jsonResponse`, `BASE_URL` sẵn có — **không dựng khung giả lập thứ hai**:

```ts
  it('getPracticeCards gọi GET /api/srs/practice với limit', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await client.getPracticeCards(30);

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/api/srs/practice');
    expect(calledUrl).toContain('limit=30');
  });

  it('submitPractice gọi POST /api/srs/practice', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await client.submitPractice({ cardId: 7, rating: 'GOOD' });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/srs/practice`,
      expect.objectContaining({ method: 'POST' }),
    );
  });
```

Thêm `getPracticeCards: vi.fn(),` và `submitPractice: vi.fn(),` vào object `api` (quanh dòng 12) của `extension/src/background/service-worker.test.ts`, rồi thêm ca test cạnh ca `SUBMIT_REVIEW`. Dùng helper `send()` và biến `refreshBadge` sẵn có:

```ts
  it('SUBMIT_PRACTICE gọi submitPractice và KHÔNG đụng badge', async () => {
    await loadServiceWorker();
    api.submitPractice.mockResolvedValue(null);

    const response = await send({ type: 'SUBMIT_PRACTICE', cardId: 7, rating: 'GOOD' });

    expect(api.submitPractice).toHaveBeenCalledWith({ cardId: 7, rating: 'GOOD' });
    expect(response).toEqual({ ok: true, data: null });
    // Luyện thêm KHÔNG đổi lịch, nên số thẻ đến hạn không thể đổi.
    expect(refreshBadge).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd extension && npm test -- src/background
```

Kỳ vọng: FAIL — `client.getPracticeCards is not a function`.

- [ ] **Step 3a: `shared/types.ts`**

Thêm vào `DailyPoint`:

```ts
export interface DailyPoint {
  date: string;
  reviews: number;
  /**
   * Số lượt luyện thêm trong ngày. Field RIÊNG chứ không cộng vào `reviews`: `reviews` giữ
   * nguyên nghĩa "lượt ôn theo lịch", và streak chỉ đếm nó.
   */
  practice: number;
}
```

- [ ] **Step 3b: `shared/messages.ts`**

Thêm interface cạnh `GetDueCardsRequest`:

```ts
/** Xấp thẻ luyện thêm — mọi từ đã học, xáo ngẫu nhiên. Không có khái niệm "đến hạn". */
export interface GetPracticeCardsRequest {
  type: 'GET_PRACTICE_CARDS';
  limit: number;
}

/**
 * Một lượt luyện thêm. KHÔNG đổi lịch SM-2 — đó là toàn bộ điểm khác biệt với
 * `SUBMIT_REVIEW`. Gửi nhầm cái này cho một lượt ôn thật thì lịch đứng yên mãi mãi.
 */
export interface SubmitPracticeRequest {
  type: 'SUBMIT_PRACTICE';
  cardId: number;
  rating: Rating;
}
```

Thêm vào union `ExtensionRequest`, ngay sau `SubmitReviewRequest`:

```ts
  | GetPracticeCardsRequest
  | SubmitPracticeRequest
```

Thêm vào `ResponseMap`, ngay sau `SUBMIT_REVIEW`:

```ts
  GET_PRACTICE_CARDS: CardDto[];
  SUBMIT_PRACTICE: null;
```

- [ ] **Step 3c: `background/api-client.ts`**

Thêm ngay sau `submitReview`:

```ts
  /** Xấp thẻ luyện thêm. Không có `newLimit` — chế độ này không có khái niệm "đến hạn". */
  async getPracticeCards(limit: number): Promise<CardDto[]> {
    return this.request(`/api/srs/practice?limit=${limit}`, { method: 'GET' });
  }

  /** Ghi một lượt luyện thêm. Backend trả 204 nên không có gì để đọc. */
  async submitPractice(args: { cardId: number; rating: Rating }): Promise<null> {
    await this.request<null>('/api/srs/practice', {
      method: 'POST',
      body: JSON.stringify(args),
    });
    return null;
  }
```

- [ ] **Step 3d: `background/service-worker.ts`**

Ngay sau nhánh `SUBMIT_REVIEW`:

```ts
    case 'GET_PRACTICE_CARDS':
      return client.getPracticeCards(request.limit);
    case 'SUBMIT_PRACTICE':
      // KHÔNG gọi refreshBadge: luyện thêm không đụng lịch, nên số thẻ đến hạn không thể
      // đổi vì một lượt luyện.
      return client.submitPractice({ cardId: request.cardId, rating: request.rating });
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd extension && npm test && npm run build
```

`npm run build` sẽ đỏ ở mọi fixture `DailyPoint` thiếu `practice`. Đó là hệ quả ĐÚNG của việc thêm field bắt buộc vào mirror — thêm `practice: 0` vào từng fixture, **đừng** khai `practice?: number` cho build hết đỏ (ràng buộc #3 cấm optional trong mirror).

Hai file có fixture đó: `src/sidepanel/StatsCharts.test.tsx` và `src/sidepanel/StatsTab.test.tsx`.

- [ ] **Step 5: Commit**

```bash
git add extension/src/shared/types.ts extension/src/shared/messages.ts \
        extension/src/background/api-client.ts extension/src/background/service-worker.ts \
        extension/src/background/api-client.test.ts extension/src/background/service-worker.test.ts \
        extension/src/sidepanel/StatsCharts.test.tsx extension/src/sidepanel/StatsTab.test.tsx
git commit -m "feat(ext): nối dây luyện thêm qua service worker"
```

---

## Task 7: `ReviewTab` — chế độ luyện và hàng đợi học lại

**Đây là task khó nhất phía extension.** Quy tắc ở Step 3b là trung tâm.

**Files:**
- Modify: `extension/src/sidepanel/ReviewTab.tsx`
- Test: `extension/src/sidepanel/ReviewTab.test.tsx`

**Interfaces:**
- Consumes: `GET_PRACTICE_CARDS`, `SUBMIT_PRACTICE` (Task 6)
- Produces: không gì

- [ ] **Step 1: Viết test đỏ**

Thêm vào `extension/src/sidepanel/ReviewTab.test.tsx` (đọc file trước, dùng lại helper `card()`, `mockQueue()`, `optionText()`, `isCorrectFor()` sẵn có):

```tsx
/** Ghi lại mọi message gửi đi để đếm và kiểm thứ tự. */
function mockWithLog(cards: CardDto[], practice: CardDto[] = []) {
  const sent: { type: string; cardId?: number }[] = [];
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string; cardId?: number }) => {
      sent.push({ type: request.type, cardId: request.cardId });
      if (request.type === 'GET_DUE_CARDS') return { ok: true, data: cards };
      if (request.type === 'GET_PRACTICE_CARDS') return { ok: true, data: practice };
      if (request.type === 'SUBMIT_REVIEW') return OK_REVIEW;
      return { ok: true, data: null };
    },
  );
  return sent;
}

/** Nút lựa chọn mở đầu bằng số thứ tự. Trả nút SAI cho thẻ `term`. */
async function nutSai(term: string): Promise<HTMLElement> {
  const nut = (await screen.findAllByRole('button')).find(
    (b) => /^\d/.test(b.textContent ?? '') && !isCorrectFor(term, b),
  );
  if (!nut) throw new Error(`Không tìm thấy nút sai cho "${term}"`);
  return nut;
}

it('trả lời sai rồi trả lời lại gửi đúng một SUBMIT_REVIEW rồi một SUBMIT_PRACTICE', async () => {
  // QUY TẮC TRUNG TÂM của cả tính năng: mỗi thẻ đóng góp NHIỀU NHẤT MỘT lượt SCHEDULED
  // trong một buổi. Mọi lần hiện lại đều là PRACTICE.
  //
  // Nếu lượt thứ hai cũng gửi SUBMIT_REVIEW, nó tính tiếp từ trạng thái vừa lapse và đẩy
  // interval lên lại — tức là trả lời đúng ở lần thứ hai XOÁ MẤT dấu vết đã quên.
  //
  // Dùng ĐÚNG MỘT thẻ: với xấp 1 phần tử, thẻ chèn lại rơi vào index 1 nên chỉ cần bấm
  // "Tiếp" một lần là nó quay lại. Ba thẻ thì phải bấm ba lần và test dài gấp đôi mà không
  // kiểm thêm được gì.
  const sent = mockWithLog([card(1, 'mitigate')]);
  render(<ReviewTab />);

  await userEvent.click(await nutSai('mitigate'));
  await userEvent.click(screen.getByRole('button', { name: 'Tiếp' }));
  await userEvent.click(await nutSai('mitigate'));

  expect(sent.filter((s) => s.type === 'SUBMIT_REVIEW')).toHaveLength(1);
  expect(sent.filter((s) => s.type === 'SUBMIT_PRACTICE')).toHaveLength(1);
  // Thứ tự cũng là hợp đồng: lượt theo lịch phải đi TRƯỚC.
  const chiHaiLoai = sent
    .map((s) => s.type)
    .filter((t) => t === 'SUBMIT_REVIEW' || t === 'SUBMIT_PRACTICE');
  expect(chiHaiLoai).toEqual(['SUBMIT_REVIEW', 'SUBMIT_PRACTICE']);
});

it('thẻ trả lời sai hiện lại trong xấp', async () => {
  // Bộ đếm render dạng `{index + 1}/{questions.length}` (ReviewTab.tsx:147).
  mockWithLog([card(1, 'mitigate'), card(2, 'robust')]);
  render(<ReviewTab />);
  expect(await screen.findByText('1/2')).toBeInTheDocument();

  await userEvent.click(await nutSai('mitigate'));

  // Xấp 2 thẻ; sai một thẻ thì tổng phải thành 3, vị trí hiện tại vẫn là 1.
  expect(screen.getByText('1/3')).toBeInTheDocument();
});

it('hết hàng đợi thì hiện nút Luyện thêm', async () => {
  mockWithLog([]);
  render(<ReviewTab />);

  expect(await screen.findByRole('button', { name: 'Luyện thêm' })).toBeInTheDocument();
});

it('vào chế độ luyện thì hiện dòng cảnh báo không ảnh hưởng lịch', async () => {
  mockWithLog([], [card(9, 'resilient')]);
  render(<ReviewTab />);

  await userEvent.click(await screen.findByRole('button', { name: 'Luyện thêm' }));

  expect(await screen.findByText(/không ảnh hưởng lịch ôn/)).toBeInTheDocument();
});

it('trả lời trong chế độ luyện chỉ gửi SUBMIT_PRACTICE', async () => {
  const sent = mockWithLog([], [card(9, 'resilient'), card(10, 'coherent')]);
  render(<ReviewTab />);
  await userEvent.click(await screen.findByRole('button', { name: 'Luyện thêm' }));

  const nut = (await screen.findAllByRole('button')).find((b) => /^\d/.test(b.textContent ?? ''));
  await userEvent.click(nut!);

  expect(sent.filter((s) => s.type === 'SUBMIT_REVIEW')).toHaveLength(0);
  expect(sent.filter((s) => s.type === 'SUBMIT_PRACTICE')).toHaveLength(1);
});
```

Text trong các query trên đã đối chiếu với `ReviewTab.tsx` thật: nút chuyển thẻ là `Tiếp` (dòng 241), bộ đếm là `{index + 1}/{questions.length}` (dòng 147). Không phải phỏng đoán.

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd extension && npm test -- src/sidepanel/ReviewTab.test.tsx
```

- [ ] **Step 3a: Thêm chế độ vào `ReviewTab.tsx`**

```tsx
type Mode = 'scheduled' | 'practice';

/** Số thẻ xen vào trước khi thẻ vừa quên hiện lại. Tương đương "learning step" của Anki,
 *  nhưng đo bằng số thẻ chứ không bằng phút — panel không có lịch trong ngày. */
const RELEARN_GAP = 3;
const PRACTICE_LIMIT = 30;
```

State:

```tsx
const [mode, setMode] = useState<Mode>('scheduled');
// Thẻ đã gửi một lượt SCHEDULED trong buổi này. Dùng ref chứ không state: giá trị này
// không ảnh hưởng render, và đọc nó trong handler phải luôn thấy giá trị mới nhất.
const scheduledSent = useRef<Set<number>>(new Set());
```

`load()` nhận `nextMode` và xoá `scheduledSent`:

```tsx
const load = useCallback(async (nextMode: Mode = 'scheduled') => {
  setLoading(true);
  scheduledSent.current = new Set();
  const response = nextMode === 'practice'
    ? await sendToBackground({ type: 'GET_PRACTICE_CARDS', limit: PRACTICE_LIMIT })
    : await sendToBackground({
        type: 'GET_DUE_CARDS',
        limit: QUEUE_LIMIT,
        newLimit: (await loadSettings()).newWordsPerDay,
      });
  // …phần dựng questions giữ nguyên như hiện tại…
  setMode(nextMode);
}, []);
```

- [ ] **Step 3b: Quy tắc gửi — phần quan trọng nhất**

```tsx
async function submit(rating: Rating, cardId: number) {
  setLastRating(rating);
  setSubmitting(true);

  // Mỗi thẻ đóng góp NHIỀU NHẤT MỘT lượt SCHEDULED trong một buổi. Mọi lần hiện lại đều là
  // PRACTICE.
  //
  // Lượt đầu đã kéo lịch về gần — đúng, đó là một lần quên. Nếu lượt thứ hai cũng gửi
  // SUBMIT_REVIEW, nó tính tiếp từ trạng thái vừa lapse và đẩy interval lên lại, tức là trả
  // lời đúng ở lần thứ hai xoá mất dấu vết đã quên.
  const laLuotOnDauTien = mode === 'scheduled' && !scheduledSent.current.has(cardId);

  const response = laLuotOnDauTien
    ? await sendToBackground({ type: 'SUBMIT_REVIEW', cardId, rating })
    : await sendToBackground({ type: 'SUBMIT_PRACTICE', cardId, rating });

  if (laLuotOnDauTien) scheduledSent.current.add(cardId);

  setSubmitting(false);
  setError(response.ok ? null : response.error);
}
```

Chèn lại thẻ trả lời sai, trong `choose()` sau khi `submit()` xong:

```tsx
if (!correct) {
  setQuestions((qs) => {
    const at = Math.min(index + 1 + RELEARN_GAP, qs.length);
    const next = [...qs];
    next.splice(at, 0, question);
    return next;
  });
}
```

- [ ] **Step 3c: Nút Luyện thêm và dòng cảnh báo**

Trong nhánh `if (!question)` (trạng thái rỗng), thêm nút:

```tsx
        <button type="button" onClick={() => void load('practice')}>Luyện thêm</button>
```

Phía trên xấp thẻ, khi `mode === 'practice'`:

```tsx
      {mode === 'practice' && (
        <div className="practice-banner">
          <span>Luyện thêm — không ảnh hưởng lịch ôn</span>
          <button type="button" onClick={() => void load('scheduled')}>Quay lại</button>
        </div>
      )}
```

Dòng đó bắt buộc: không có nó, người dùng trả lời hai chục thẻ rồi thấy badge không giảm và kết luận phần mềm hỏng.

- [ ] **Step 3d: CSS cho banner**

Thêm vào cuối `extension/src/sidepanel/styles.css`:

```css
/* Dải nhắc chế độ luyện thêm — người dùng phải biết lịch không đang chạy. */
.practice-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 10px;
  border-radius: var(--r-control);
  background: var(--accent-soft);
  color: var(--accent-text);
  font-size: 12.5px;
}
.practice-banner button {
  padding: 4px 10px;
  border: 1px solid var(--border-strong);
  border-radius: var(--r-control);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd extension && npm test && npm run build
```

- [ ] **Step 5: Chứng minh quy tắc một-SCHEDULED-mỗi-buổi bắt được lỗi**

Tạm đổi `laLuotOnDauTien` thành `mode === 'scheduled'` (bỏ phần kiểm `scheduledSent`), chạy ca `trả lời sai rồi đúng` — phải **ĐỎ**. Khôi phục, chạy lại xanh. Dán cả hai output.

- [ ] **Step 6: Commit**

```bash
git add extension/src/sidepanel/ReviewTab.tsx extension/src/sidepanel/ReviewTab.test.tsx \
        extension/src/sidepanel/styles.css
git commit -m "feat(ext): chế độ luyện thêm và hàng đợi học lại trong buổi"
```

---

## Task 8: `StatsCharts` hiện lượt luyện, và nhãn Options

**Files:**
- Modify: `extension/src/sidepanel/StatsCharts.tsx`
- Modify: `extension/src/options/Options.tsx` (dòng 75)
- Test: `extension/src/sidepanel/StatsCharts.test.tsx`, `extension/src/options/Options.test.tsx`

**Interfaces:**
- Consumes: `DailyPoint.practice` (Task 6)
- Produces: không gì

- [ ] **Step 1: Viết test đỏ**

Thêm vào `extension/src/sidepanel/StatsCharts.test.tsx`:

```tsx
it('chiều cao cột tính cả lượt luyện thêm', () => {
  render(
    <DailyBars
      daily={[
        { date: '2026-08-10', reviews: 2, practice: 0 },
        { date: '2026-08-11', reviews: 2, practice: 8 },
      ]}
    />,
  );

  const bars = screen.getAllByTestId('bar');
  // Ngày sau có 10 lượt so với 2 lượt của ngày trước — cột phải cao hơn hẳn.
  expect(parseFloat(bars[1].style.height)).toBeGreaterThan(parseFloat(bars[0].style.height));
});

it('title tách riêng lượt ôn và lượt luyện thêm', () => {
  render(<Heatmap daily={[{ date: '2026-08-11', reviews: 12, practice: 5 }]} />);

  expect(screen.getByTestId('cell')).toHaveAttribute(
    'title',
    '11/08: 12 lượt ôn · 5 lượt luyện thêm',
  );
});

it('ngày không luyện thêm thì title không nhắc tới nó', () => {
  render(<Heatmap daily={[{ date: '2026-08-11', reviews: 12, practice: 0 }]} />);

  expect(screen.getByTestId('cell')).toHaveAttribute('title', '11/08: 12 lượt ôn');
});
```

Thêm vào `extension/src/options/Options.test.tsx`:

```tsx
it('nhãn từ mới mỗi ngày nói rõ 0 là không giới hạn', async () => {
  render(<Options />);

  expect(await screen.findByLabelText(/Từ mới mỗi ngày \(0 = không giới hạn\)/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd extension && npm test -- src/sidepanel/StatsCharts.test.tsx src/options/Options.test.tsx
```

- [ ] **Step 3a: `StatsCharts.tsx`**

Thêm hàm gộp và hàm dựng nhãn, cạnh `formatDayMonth`:

```tsx
/** Tổng công sức của một ngày. Công sức là công sức — cột và độ đậm ô tính cả hai loại. */
function totalOf(point: DailyPoint): number {
  return point.reviews + point.practice;
}

/**
 * Nhãn rê chuột. Tách riêng hai con số vì đây là CHỖ DUY NHẤT giải thích được vì sao một
 * ngày có ô tô đậm mà streak vẫn đứt: hôm đó chỉ luyện thêm, không ôn theo lịch.
 */
function cellTitle(point: DailyPoint): string {
  const base = `${formatDayMonth(point.date)}: ${point.reviews} lượt ôn`;
  return point.practice > 0 ? `${base} · ${point.practice} lượt luyện thêm` : base;
}
```

Trong `DailyBars`: đổi `d.reviews` thành `totalOf(d)` ở phép tính `max`, ở chiều cao, và ở `title` (dùng `cellTitle(d)`).

Trong `Heatmap`: `buildHeatmap` nhận `daily` đã ánh xạ sang tổng, còn `title` lấy từ `cellTitle` của điểm gốc:

```tsx
  const columns = buildHeatmap(daily.map((d) => ({ ...d, reviews: totalOf(d) })));
  const titleByDate = new Map(daily.map((d) => [d.date, cellTitle(d)]));
```

rồi trong JSX của ô: `title={titleByDate.get(cell.date) ?? ''}`.

Cũng đổi `activeDaysInWindow` và `busiest` sang dùng `totalOf`.

- [ ] **Step 3b: `options/Options.tsx` dòng 75**

```tsx
      <label htmlFor="newWordsPerDay">Từ mới mỗi ngày (0 = không giới hạn)</label>
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd extension && npm test && npm run build
```

- [ ] **Step 5: Chạy đủ bốn cổng nghiệm thu**

```bash
cd api-service && uv run pytest && uv run mypy app && uv run ruff check .
```

```bash
cd extension && npm test && npm run build
```

Dán output thật của cả bốn.

- [ ] **Step 6: Commit**

```bash
git add extension/src/sidepanel/StatsCharts.tsx extension/src/sidepanel/StatsCharts.test.tsx \
        extension/src/options/Options.tsx extension/src/options/Options.test.tsx
git commit -m "feat(ext): biểu đồ hiện lượt luyện thêm, nhãn hạn mức nói rõ 0 là bỏ giới hạn"
```

---

## Việc phải làm tay sau khi merge

**Chạy `migrations/V8__review_log_mode.sql` một lần trên Supabase.** Migration không chạy lúc cold start trên Vercel (ràng buộc #15) — quên bước này thì mọi lượt ôn chết vì cột `mode` không tồn tại.

Trên Docker/local thì `app/startup.py` tự chạy, không cần làm gì.
