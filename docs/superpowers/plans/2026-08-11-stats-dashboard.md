# Màn thống kê tiến độ học — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm tab "Thống kê" ở side panel hiển thị streak, biểu đồ cột 30 ngày, heatmap 91 ngày và độ chính xác ôn + quiz, đọc từ một endpoint mới `GET /api/stats`.

**Architecture:** Backend thêm package chỉ-đọc `app/stats/` với ba câu `GROUP BY` chạy trực tiếp trên `review_log` và `quiz_attempt` — không bảng mới, không migration, không cột mới. Extension thêm một tab đọc dữ liệu qua service worker và vẽ biểu đồ bằng `div` + CSS, không thư viện.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 sync + Postgres 16 (backend); React 18 + TypeScript 5.7 + Vitest + RTL (extension).

**Spec:** [`docs/superpowers/specs/2026-08-11-stats-dashboard-design.md`](../specs/2026-08-11-stats-dashboard-design.md)

## Global Constraints

Mọi task đều phải tuân thủ, không nhắc lại ở từng task:

- **Ngôn ngữ:** comment, docstring, message lỗi, text hiển thị viết **tiếng Việt đủ dấu**. Tên class/biến/hàm/module giữ tiếng Anh. Lưu UTF-8.
- **Không thêm dependency** (ràng buộc #12). Không Recharts, Chart.js, D3, date-fns, dayjs. Biểu đồ vẽ bằng `div` + CSS.
- **Không migration, không bảng mới, không cột mới.** Nếu một task khiến bạn muốn viết `V8__*.sql`, dừng lại — bạn đã đi chệch spec.
- **Side panel / Options / content script KHÔNG gọi HTTP** (ràng buộc #1). Mọi request đi qua `background/api-client.ts`.
- **Hợp đồng message ở `shared/messages.ts`** (ràng buộc #2): thêm interface request → thêm vào union `ExtensionRequest` → thêm vào `ResponseMap`, rồi mới xử lý ở service worker.
- **`shared/types.ts` là bản gương của DTO backend** (ràng buộc #3). Backend phát camelCase qua `ApiModel`; mirror khai `T | null` chứ không optional.
- **Mọi truy vấn chạm dữ liệu học phải lọc `vocab_entry.user_id`** (ràng buộc #13). `GET /api/stats` phải có mặt trong `tests/test_multi_user_isolation.py`.
- **Không thêm mã lỗi mới** vào `common/errors.py`.
- **Đặt tên file test backend đúng `test_*.py` trong `tests/`** — sai tên là test bị bỏ qua **im lặng**.
- **Cổng nghiệm thu cuối:** `uv run pytest` + `uv run mypy app` + `uv run ruff check .` (cwd `api-service/`), `npm test` + `npm run build` (cwd `extension/`). Test xanh mà mypy/build đỏ vẫn là hỏng.

## File Structure

**Backend — `api-service/`**

| File | Trách nhiệm |
|---|---|
| `app/stats/__init__.py` | rỗng |
| `app/stats/streak.py` | **mới** — hàm thuần tính streak từ `list[date]`. Không import `Session`, không gọi `date.today()` |
| `app/stats/repository.py` | **mới** — đúng ba câu truy vấn. Chỗ duy nhất trong package chạm DB |
| `app/stats/models.py` | **mới** — chỉ DTO Pydantic. **Không** SQLAlchemy entity |
| `app/stats/service.py` | **mới** — ghép repository + streak thành `StatsDto`, bơm đầy 91 ngày |
| `app/stats/router.py` | **mới** — `GET /api/stats` |
| `app/main.py` | sửa — đăng ký router |
| `tests/test_stats_streak.py` | **mới** — hàm thuần, không chạm DB |
| `tests/test_stats_repository.py` | **mới** — ba câu truy vấn, gồm ca múi giờ |
| `tests/test_stats_endpoint.py` | **mới** — hợp đồng JSON |
| `tests/test_multi_user_isolation.py` | sửa — thêm ca cho `/api/stats` |

**Extension — `extension/src/`**

| File | Trách nhiệm |
|---|---|
| `shared/types.ts` | sửa — mirror DTO |
| `shared/messages.ts` | sửa — `GetStatsRequest` |
| `shared/heatmap.ts` | **mới** — hàm thuần dựng lưới + thang màu |
| `shared/heatmap.test.ts` | **mới** |
| `background/api-client.ts` | sửa — `learningStats()` |
| `background/service-worker.ts` | sửa — nhánh `GET_STATS` |
| `sidepanel/StatsCharts.tsx` | **mới** — bốn component vẽ thuần, **chỉ nhận props, không fetch** |
| `sidepanel/StatsCharts.test.tsx` | **mới** |
| `sidepanel/StatsTab.tsx` | **mới** — nạp dữ liệu + bốn trạng thái + bố cục |
| `sidepanel/StatsTab.test.tsx` | **mới** |
| `sidepanel/App.tsx` | sửa — tab thứ 5 |
| `sidepanel/styles.css` | sửa — style biểu đồ |

Tách `StatsCharts.tsx` khỏi `StatsTab.tsx` vì `QuizTab.tsx` đã phình tới 19.5K do gộp nạp dữ liệu với vẽ. Component vẽ chỉ nhận props nên test bằng fixture thẳng, không cần giả lập `chrome.runtime.sendMessage`.

## Trước khi bắt đầu

- [ ] **Dọn việc đang dở ở `styles.css`**

Nhánh `feat/manual-text-input` đang có 6 tệp sửa chưa commit, trong đó `styles.css` sửa 812 dòng. Task 9 cũng thêm style vào đúng tệp đó.

```bash
git status --short
```

Nếu `extension/src/sidepanel/styles.css` còn trong danh sách: commit phần đang dở, hoặc `git stash`, trước khi chạy Task 1. Trộn hai luồng thay đổi vào cùng một tệp CSS 800+ dòng làm mọi lần `git diff` sau đó không đọc được, và nếu phải revert thì không tách ra được nữa.

## Thứ tự và phụ thuộc

```
Task 1 (streak.py) ─┐
Task 2 (repository) ─┴→ Task 3 (models+service+router) → Task 4 (isolation test)
                                                              │
Task 5 (wiring extension) ←───────────────────────────────────┘
Task 6 (heatmap.ts) ─┐
                     ├→ Task 7 (StatsCharts) → Task 8 (StatsTab) → Task 9 (App + CSS)
Task 5 ──────────────┘
```

Task 1, 2, 6 độc lập nhau hoàn toàn — làm song song được.

---

## Task 1: `stats/streak.py` — hàm thuần tính streak

**Files:**
- Create: `api-service/app/stats/__init__.py` (rỗng)
- Create: `api-service/app/stats/streak.py`
- Test: `api-service/tests/test_stats_streak.py`

**Interfaces:**
- Consumes: không gì
- Produces: `Streak` (dataclass đóng băng: `current: int`, `longest: int`, `last_active: date | None`) và `tinh_streak(active_days: list[date], today: date) -> Streak`

- [ ] **Step 1: Viết test đỏ**

Tạo `api-service/tests/test_stats_streak.py`:

```python
"""Streak là hàm thuần — KHÔNG chạm DB, không fixture `db`/`client`.

`today` là tham số chứ không phải `date.today()` gọi bên trong: đó là điều kiện duy nhất để
test được "hôm nay chưa ôn thì streak vẫn tính từ hôm qua" mà không phải giả lập đồng hồ.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.stats.streak import tinh_streak

HOM_NAY = date(2026, 8, 11)


def _truoc(so_ngay: int) -> date:
    return HOM_NAY - timedelta(days=so_ngay)


def test_chua_on_ngay_nao() -> None:
    ket_qua = tinh_streak([], HOM_NAY)
    assert ket_qua.current == 0
    assert ket_qua.longest == 0
    assert ket_qua.last_active is None


def test_chi_on_hom_nay() -> None:
    ket_qua = tinh_streak([HOM_NAY], HOM_NAY)
    assert ket_qua.current == 1
    assert ket_qua.longest == 1
    assert ket_qua.last_active == HOM_NAY


def test_chi_on_hom_qua_van_giu_streak() -> None:
    """9 giờ sáng chưa kịp ôn mà thấy streak về 0 là sai, và sai đúng lúc phản tác dụng
    nhất. Streak chỉ đứt khi CẢ hôm nay lẫn hôm qua đều trống."""
    ket_qua = tinh_streak([_truoc(1)], HOM_NAY)
    assert ket_qua.current == 1
    assert ket_qua.last_active == _truoc(1)


def test_on_lan_cuoi_cach_day_hai_ngay_thi_dut() -> None:
    ket_qua = tinh_streak([_truoc(2)], HOM_NAY)
    assert ket_qua.current == 0
    assert ket_qua.longest == 1
    assert ket_qua.last_active == _truoc(2)


def test_ba_ngay_lien_tiep_ket_thuc_hom_nay() -> None:
    ket_qua = tinh_streak([_truoc(2), _truoc(1), HOM_NAY], HOM_NAY)
    assert ket_qua.current == 3
    assert ket_qua.longest == 3


def test_ba_ngay_lien_tiep_ket_thuc_hom_qua() -> None:
    ket_qua = tinh_streak([_truoc(3), _truoc(2), _truoc(1)], HOM_NAY)
    assert ket_qua.current == 3
    assert ket_qua.longest == 3


def test_chuoi_dai_nhat_nam_o_qua_khu() -> None:
    """current và longest là hai con số khác nhau — trả cùng một giá trị cho cả hai là lỗi
    dễ lọt nhất ở đây."""
    ngay = [_truoc(n) for n in (20, 19, 18, 17, 16)] + [_truoc(1), HOM_NAY]
    ket_qua = tinh_streak(sorted(ngay), HOM_NAY)
    assert ket_qua.current == 2
    assert ket_qua.longest == 5
    assert ket_qua.last_active == HOM_NAY


def test_mot_ngay_duy_nhat_cach_day_mot_nam() -> None:
    xa = HOM_NAY - timedelta(days=365)
    ket_qua = tinh_streak([xa], HOM_NAY)
    assert ket_qua.current == 0
    assert ket_qua.longest == 1
    assert ket_qua.last_active == xa
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd api-service && uv run pytest tests/test_stats_streak.py -v
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'app.stats'`.

- [ ] **Step 3: Viết implementation tối thiểu**

Tạo `api-service/app/stats/__init__.py` rỗng, và `api-service/app/stats/streak.py`:

```python
"""Tính streak từ danh sách ngày có lượt ôn.

Hàm thuần: không chạm `Session`, không gọi `date.today()` bên trong. Tách khỏi `service.py`
cùng lý do `srs/scheduler.py` tách khỏi `srs/service.py` — logic ngày tháng là chỗ off-by-one
sống lâu nhất, và nó chỉ test được tử tế khi `today` là tham số.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Streak:
    current: int
    longest: int
    last_active: date | None


def tinh_streak(active_days: list[date], today: date) -> Streak:
    """`active_days` phải đã sắp xếp TĂNG DẦN và không trùng lặp — repository đảm bảo cả hai
    bằng `GROUP BY ngay ORDER BY ngay`.

    Hôm nay chưa ôn thì streak VẪN tính từ hôm qua. Streak chỉ đứt khi cả hôm nay lẫn hôm qua
    đều trống — đúng cách Anki và Duolingo làm.
    """
    if not active_days:
        return Streak(current=0, longest=0, last_active=None)

    co_on = set(active_days)
    longest = _chuoi_dai_nhat(active_days)
    last_active = active_days[-1]

    moc = today if today in co_on else today - timedelta(days=1)
    if moc not in co_on:
        return Streak(current=0, longest=longest, last_active=last_active)

    current = 0
    while moc in co_on:
        current += 1
        moc -= timedelta(days=1)

    return Streak(current=current, longest=longest, last_active=last_active)


def _chuoi_dai_nhat(days: list[date]) -> int:
    """Chuỗi ngày liên tiếp dài nhất trong toàn bộ lịch sử. `days` khác rỗng."""
    dai_nhat = 1
    hien_tai = 1
    for truoc, sau in zip(days, days[1:], strict=False):
        hien_tai = hien_tai + 1 if sau - truoc == timedelta(days=1) else 1
        dai_nhat = max(dai_nhat, hien_tai)
    return dai_nhat
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd api-service && uv run pytest tests/test_stats_streak.py -v && uv run mypy app && uv run ruff check .
```

Kỳ vọng: 8 passed, mypy `Success`, ruff `All checks passed`.

- [ ] **Step 5: Commit**

```bash
git add api-service/app/stats/__init__.py api-service/app/stats/streak.py api-service/tests/test_stats_streak.py
git commit -m "feat(stats): hàm thuần tính streak ngày ôn liên tiếp"
```

---

## Task 2: `stats/repository.py` — ba câu truy vấn

**Files:**
- Create: `api-service/app/stats/repository.py`
- Test: `api-service/tests/test_stats_repository.py`

**Interfaces:**
- Consumes: không gì (độc lập với Task 1)
- Produces: ba hàm —
  - `dem_luot_on_theo_ngay(db: Session, user_id: int) -> list[tuple[date, int]]` (tăng dần theo ngày)
  - `dem_luot_on_theo_rating(db: Session, user_id: int) -> dict[str, int]` (khoá là `"AGAIN" | "HARD" | "GOOD" | "EASY"`)
  - `thong_ke_quiz_theo_loai(db: Session, user_id: int) -> dict[str, tuple[int, int, float | None]]` (khoá là giá trị `QuizType`; tuple là `(attempts, correct, avg_score)`)

- [ ] **Step 1: Viết test đỏ**

Tạo `api-service/tests/test_stats_repository.py`:

```python
"""Ba câu truy vấn của màn thống kê.

Test ở tầng repository chứ không chỉ qua HTTP: ca múi giờ dưới đây là lỗi nguy hiểm nhất của
cả tính năng, và nó chỉ nhìn thấy rõ khi so trực tiếp `date` trả về.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.stats import repository as repo
from tests.conftest import NguoiDungTest


def _seed_the(db: Session, user_id: int, term: str) -> int:
    """Một từ kèm thẻ SRS. Trả về `srs_card.id`."""
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id) "
                "VALUES (:t, :t, 'en', 'verb', 'nghĩa', :u) RETURNING id"
            ),
            {"t": term, "u": user_id},
        ).scalar_one()
    )
    return int(
        db.execute(
            text(
                "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions) "
                "VALUES (:v, CURRENT_DATE, 'REVIEW', 2) RETURNING id"
            ),
            {"v": vocab_id},
        ).scalar_one()
    )


def _seed_luot_on(db: Session, card_id: int, rating: str, luc: str) -> None:
    """`luc` là timestamptz dạng chuỗi, ví dụ '2026-08-11 18:00:00+00'."""
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, reviewed_at) "
            "VALUES (:c, :r, 0, 1, :t::timestamptz)"
        ),
        {"c": card_id, "r": rating, "t": luc},
    )


def test_luot_on_luc_1h_sang_gio_viet_nam_thuoc_ve_ngay_hom_do(
    db: Session, owner: NguoiDungTest
) -> None:
    """Ca phân biệt DUY NHẤT của lỗi múi giờ, và nó phải là 1 giờ sáng chứ không phải buổi tối.

    `reviewed_at` là TIMESTAMPTZ. 18:00 UTC ngày 11/8 chính là 01:00 sáng ngày 12/8 giờ Việt
    Nam (UTC+7). Viết `reviewed_at::date` trần thì Postgres quy về UTC và trả 11/8 — lượt ôn
    bị đẩy lùi một ngày, streak đứt sai, không có exception nào.

    Buổi tối KHÔNG phân biệt được: 20:00 giờ VN là 13:00 UTC, vẫn cùng ngày, nên code sai vẫn
    cho kết quả đúng.
    """
    card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot_on(db, card_id, "GOOD", "2026-08-11 18:00:00+00")
    db.commit()

    assert repo.dem_luot_on_theo_ngay(db, owner.id) == [(date(2026, 8, 12), 1)]


def test_gom_theo_ngay_tra_ve_tang_dan_va_dem_dung(db: Session, owner: NguoiDungTest) -> None:
    card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot_on(db, card_id, "GOOD", "2026-08-10 05:00:00+00")
    _seed_luot_on(db, card_id, "HARD", "2026-08-10 06:00:00+00")
    _seed_luot_on(db, card_id, "EASY", "2026-08-08 05:00:00+00")
    db.commit()

    assert repo.dem_luot_on_theo_ngay(db, owner.id) == [
        (date(2026, 8, 8), 1),
        (date(2026, 8, 10), 2),
    ]


def test_gom_theo_rating(db: Session, owner: NguoiDungTest) -> None:
    card_id = _seed_the(db, owner.id, "mitigate")
    for rating in ("AGAIN", "GOOD", "GOOD", "EASY"):
        _seed_luot_on(db, card_id, rating, "2026-08-10 05:00:00+00")
    db.commit()

    assert repo.dem_luot_on_theo_rating(db, owner.id) == {"AGAIN": 1, "GOOD": 2, "EASY": 1}


def test_thong_ke_quiz_theo_loai(db: Session, owner: NguoiDungTest) -> None:
    """`avg_score` trả về nguyên trạng cho MỌI loại; việc bỏ nó đi với hai loại không có khái
    niệm điểm là quyết định của service, không phải của repository."""
    card_id = _seed_the(db, owner.id, "mitigate")
    vocab_id = int(
        db.execute(
            text("SELECT vocab_entry_id FROM srs_card WHERE id = :c"), {"c": card_id}
        ).scalar_one()
    )
    item_id = int(
        db.execute(
            text(
                "INSERT INTO quiz_item (vocab_entry_id, type, payload, prompt_version) "
                "VALUES (:v, 'FREE_WRITE', '{}'::jsonb, 1) RETURNING id"
            ),
            {"v": vocab_id},
        ).scalar_one()
    )
    for dung, diem in ((True, 90), (False, 40)):
        db.execute(
            text(
                "INSERT INTO quiz_attempt (quiz_item_id, user_answer, correct, score) "
                "VALUES (:i, 'câu trả lời', :c, :s)"
            ),
            {"i": item_id, "c": dung, "s": diem},
        )
    db.commit()

    assert repo.thong_ke_quiz_theo_loai(db, owner.id) == {"FREE_WRITE": (2, 1, 65.0)}


def test_ba_cau_deu_tra_rong_cho_nguoi_chua_lam_gi(db: Session, owner: NguoiDungTest) -> None:
    assert repo.dem_luot_on_theo_ngay(db, owner.id) == []
    assert repo.dem_luot_on_theo_rating(db, owner.id) == {}
    assert repo.thong_ke_quiz_theo_loai(db, owner.id) == {}
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd api-service && uv run pytest tests/test_stats_repository.py -v
```

Kỳ vọng: FAIL — `ImportError: cannot import name 'repository' from 'app.stats'`.

- [ ] **Step 3: Viết implementation tối thiểu**

Tạo `api-service/app/stats/repository.py`:

```python
"""Truy vấn của màn thống kê — đúng ba câu.

File này CỐ Ý đọc chéo cả ba context (srs, quiz, vocabulary). Đó là việc của một read model
báo cáo, khác `quiz/candidates.py` — file đó phải khoanh vùng vì quiz chỉ chạm dữ liệu SRS ở
đúng một chỗ và chỗ đó cần nhìn thấy bằng mắt.

Chủ sở hữu nằm ở ĐÚNG một cột — `vocab_entry.user_id` (ràng buộc #13). Không bảng nào ở đây
có cột đó, nên cả ba câu đều join về `vocab_entry` rồi lọc. Không được đẻ thêm cột `user_id`
ở `review_log` hay `quiz_attempt` cho tiện.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.config import get_settings
from app.quiz.models import QuizAttempt, QuizItem
from app.srs.models import ReviewLog, SrsCard
from app.vocabulary.models import VocabEntry


def _ngay_dia_phuong() -> ColumnElement[date]:
    """`(reviewed_at AT TIME ZONE :tz)::date` với `:tz = settings.tz`.

    TUYỆT ĐỐI không dùng `cast(ReviewLog.reviewed_at, Date)` trần: `reviewed_at` là TIMESTAMPTZ
    nên cast trần quy về UTC. Lượt ôn 01:00 sáng giờ Việt Nam bị đẩy về ngày hôm trước, streak
    đứt sai, và không có exception nào — xem `test_stats_repository.py`.
    """
    return cast(func.timezone(get_settings().tz, ReviewLog.reviewed_at), Date)


def dem_luot_on_theo_ngay(db: Session, user_id: int) -> list[tuple[date, int]]:
    """Số lượt ôn mỗi ngày trên TOÀN BỘ lịch sử, tăng dần theo ngày.

    Một câu này nuôi bốn con số: `daily` (service cắt 91 ngày cuối), `totals.reviews` (tổng),
    `totals.activeDays` (số dòng) và `streak`. Tách thành hai câu — một cho cửa sổ 91 ngày,
    một cho streak — là tạo cơ hội cho hai cửa sổ lệch nhau vào lần đầu ai đó sửa hằng số.

    Số dòng trả về bằng số NGÀY đã từng ôn, không phải số lượt: ba năm học đều là ≤1095 dòng.
    """
    ngay = _ngay_dia_phuong().label("ngay")
    cau = (
        select(ngay, func.count().label("so_luot"))
        .select_from(ReviewLog)
        .join(SrsCard, SrsCard.id == ReviewLog.card_id)
        .join(VocabEntry, VocabEntry.id == SrsCard.vocab_entry_id)
        .where(VocabEntry.user_id == user_id)
        .group_by(ngay)
        .order_by(ngay)
    )
    return [(hang[0], int(hang[1])) for hang in db.execute(cau).all()]


def dem_luot_on_theo_rating(db: Session, user_id: int) -> dict[str, int]:
    """Số lượt ôn theo từng mức tự chấm, toàn bộ lịch sử.

    Trả số lượt THÔ, không trả sẵn tỉ lệ nhớ: tỉ lệ là `1 − again/tổng`, một phép chia ở
    client. Trả cả hai là dựng hai nguồn sự thật cho cùng một con số.

    Mức chưa xuất hiện lần nào thì VẮNG khỏi dict — service tự bù 0.
    """
    cau = (
        select(ReviewLog.rating, func.count())
        .select_from(ReviewLog)
        .join(SrsCard, SrsCard.id == ReviewLog.card_id)
        .join(VocabEntry, VocabEntry.id == SrsCard.vocab_entry_id)
        .where(VocabEntry.user_id == user_id)
        .group_by(ReviewLog.rating)
    )
    return {str(hang[0]): int(hang[1]) for hang in db.execute(cau).all()}


def thong_ke_quiz_theo_loai(db: Session, user_id: int) -> dict[str, tuple[int, int, float | None]]:
    """`(số lượt, số lượt đúng, điểm trung bình)` theo từng loại quiz, toàn bộ lịch sử.

    `avg_score` trả nguyên trạng cho MỌI loại. Việc bỏ nó đi với `FILL_BLANK` và
    `COLLOCATION_CHOICE` là quyết định của service — repository chỉ đọc, không diễn giải.

    Loại chưa làm lần nào thì VẮNG khỏi dict; service tự bù hàng 0 để `quiz` luôn đủ 3 phần tử.
    """
    cau = (
        select(
            QuizItem.type,
            func.count(),
            func.count().filter(QuizAttempt.correct),
            func.avg(QuizAttempt.score),
        )
        .select_from(QuizAttempt)
        .join(QuizItem, QuizItem.id == QuizAttempt.quiz_item_id)
        .join(VocabEntry, VocabEntry.id == QuizItem.vocab_entry_id)
        .where(VocabEntry.user_id == user_id)
        .group_by(QuizItem.type)
    )
    return {
        str(hang[0]): (int(hang[1]), int(hang[2]), None if hang[3] is None else float(hang[3]))
        for hang in db.execute(cau).all()
    }
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd api-service && uv run pytest tests/test_stats_repository.py -v && uv run mypy app && uv run ruff check .
```

Kỳ vọng: 5 passed, mypy `Success`, ruff sạch.

Nếu `test_luot_on_luc_1h_sang_gio_viet_nam_thuoc_ve_ngay_hom_do` đỏ với `date(2026, 8, 11)` thay vì `12`, nghĩa là `func.timezone` không được áp dụng — kiểm lại `_ngay_dia_phuong()`, đừng sửa test.

- [ ] **Step 5: Commit**

```bash
git add api-service/app/stats/repository.py api-service/tests/test_stats_repository.py
git commit -m "feat(stats): ba câu truy vấn tổng hợp, gom ngày theo settings.tz"
```

---

## Task 3: DTO, service và endpoint `GET /api/stats`

**Files:**
- Create: `api-service/app/stats/models.py`
- Create: `api-service/app/stats/service.py`
- Create: `api-service/app/stats/router.py`
- Modify: `api-service/app/main.py` (thêm import cạnh các router khác, và `include_router` sau `quiz_router`)
- Test: `api-service/tests/test_stats_endpoint.py`

**Interfaces:**
- Consumes: `app.stats.streak.tinh_streak`, `app.stats.streak.Streak` (Task 1); `app.stats.repository.dem_luot_on_theo_ngay` / `dem_luot_on_theo_rating` / `thong_ke_quiz_theo_loai` (Task 2); `app.srs.repository.count_learned(db, user_id) -> int` (đã có sẵn)
- Produces: `GET /api/stats` trả `StatsDto`. Đây là hợp đồng mà Task 5 mirror sang TypeScript — tên khoá JSON là camelCase do `ApiModel` sinh: `streak`, `totals`, `daily`, `recall`, `quiz`; `streak.lastActiveDate`; `totals.learnedWords`, `totals.activeDays`; phần tử `quiz` có `type`, `attempts`, `correct`, `avgScore`.

- [ ] **Step 1: Viết test đỏ**

Tạo `api-service/tests/test_stats_endpoint.py`:

```python
"""Hợp đồng JSON của `GET /api/stats`.

Bốn điều kiểm ở đây là HỢP ĐỒNG, không phải chi tiết cài đặt: `daily` đủ 91 phần tử, ngày
trống được bơm 0, `avgScore` null với hai loại không có khái niệm điểm, và `quiz` luôn đủ 3
hàng đúng thứ tự. Phá một trong bốn là làm hỏng UI mà không test nào bên extension đỏ.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import NguoiDungTest


def _seed_the(db: Session, user_id: int, term: str) -> tuple[int, int]:
    """Trả `(vocab_entry_id, srs_card_id)`."""
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
                "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions) "
                "VALUES (:v, CURRENT_DATE, 'REVIEW', 2) RETURNING id"
            ),
            {"v": vocab_id},
        ).scalar_one()
    )
    return vocab_id, card_id


def _seed_luot_on_hom_nay(db: Session, card_id: int, so_luot: int) -> None:
    """`now()` chạy qua đúng đường quy đổi múi giờ như dữ liệu thật."""
    for _ in range(so_luot):
        db.execute(
            text(
                "INSERT INTO review_log (card_id, rating, prev_interval, new_interval) "
                "VALUES (:c, 'GOOD', 0, 1)"
            ),
            {"c": card_id},
        )


def _seed_quiz(db: Session, vocab_id: int, loai: str, ket_qua: list[tuple[bool, int]]) -> None:
    item_id = int(
        db.execute(
            text(
                "INSERT INTO quiz_item (vocab_entry_id, type, payload, prompt_version) "
                "VALUES (:v, :l, '{}'::jsonb, 1) RETURNING id"
            ),
            {"v": vocab_id, "l": loai},
        ).scalar_one()
    )
    for dung, diem in ket_qua:
        db.execute(
            text(
                "INSERT INTO quiz_attempt (quiz_item_id, user_answer, correct, score) "
                "VALUES (:i, 'trả lời', :c, :s)"
            ),
            {"i": item_id, "c": dung, "s": diem},
        )


def test_nguoi_dung_moi_toanh_tra_toan_so_khong_chu_khong_phai_404(
    client: Any, owner: NguoiDungTest
) -> None:
    """Chưa học gì KHÔNG phải là lỗi. Endpoint này không bao giờ trả 404."""
    resp = client.get("/api/stats", headers=owner.headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["streak"] == {"current": 0, "longest": 0, "lastActiveDate": None}
    assert body["totals"] == {"reviews": 0, "learnedWords": 0, "activeDays": 0}
    assert body["recall"] == {"again": 0, "hard": 0, "good": 0, "easy": 0}
    assert len(body["daily"]) == 91
    assert all(diem["reviews"] == 0 for diem in body["daily"])


def test_daily_luon_du_91_phan_tu_lien_tuc_va_ket_thuc_hom_nay(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Ngày không ôn được bơm `reviews: 0`. Trả mảng thưa rồi bắt client tự dựng lịch là đẩy
    phép tính ngày tháng sang chỗ không có `settings.tz`."""
    _, card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot_on_hom_nay(db, card_id, 3)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()
    daily = body["daily"]

    assert len(daily) == 91
    ngay = [date.fromisoformat(diem["date"]) for diem in daily]
    assert ngay == sorted(ngay)
    assert ngay[-1] - ngay[0] == timedelta(days=90)
    assert daily[-1]["reviews"] == 3
    assert daily[-2]["reviews"] == 0


def test_quiz_luon_du_ba_hang_dung_thu_tu_ke_ca_khi_chua_lam(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    body = client.get("/api/stats", headers=owner.headers).json()

    assert [hang["type"] for hang in body["quiz"]] == [
        "FILL_BLANK",
        "COLLOCATION_CHOICE",
        "FREE_WRITE",
    ]
    assert all(hang["attempts"] == 0 and hang["correct"] == 0 for hang in body["quiz"])
    assert all(hang["avgScore"] is None for hang in body["quiz"])


def test_avg_score_chi_co_voi_free_write(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`FILL_BLANK` và `COLLOCATION_CHOICE` chấm 100 hoặc 0, nên điểm trung bình chỉ là
    `correct/attempts` viết lại bằng đơn vị khác. `null` ở đây nghĩa là "loại này không có
    khái niệm điểm", không phải "chưa có dữ liệu"."""
    vocab_id, _ = _seed_the(db, owner.id, "mitigate")
    _seed_quiz(db, vocab_id, "FILL_BLANK", [(True, 100), (False, 0)])
    _seed_quiz(db, vocab_id, "FREE_WRITE", [(True, 80), (False, 50)])
    db.commit()

    theo_loai = {hang["type"]: hang for hang in client.get(
        "/api/stats", headers=owner.headers
    ).json()["quiz"]}

    assert theo_loai["FILL_BLANK"]["attempts"] == 2
    assert theo_loai["FILL_BLANK"]["correct"] == 1
    assert theo_loai["FILL_BLANK"]["avgScore"] is None

    assert theo_loai["FREE_WRITE"]["attempts"] == 2
    assert theo_loai["FREE_WRITE"]["avgScore"] == 65


def test_totals_va_recall_tinh_tren_toan_bo_lich_su(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Chỉ `daily` bị giới hạn 91 ngày. Lượt ôn 200 ngày trước vẫn phải vào `totals.reviews`
    và `recall` — nếu không, con số lớn sẽ tụt xuống mỗi ngày trôi qua."""
    _, card_id = _seed_the(db, owner.id, "mitigate")
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, reviewed_at) "
            "VALUES (:c, 'AGAIN', 0, 1, now() - interval '200 days')"
        ),
        {"c": card_id},
    )
    _seed_luot_on_hom_nay(db, card_id, 2)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["reviews"] == 3
    assert body["totals"]["activeDays"] == 2
    assert body["totals"]["learnedWords"] == 1
    assert body["recall"] == {"again": 1, "hard": 0, "good": 2, "easy": 0}
    # Nhưng ngày 200 hôm trước nằm NGOÀI cửa sổ, nên daily chỉ thấy 2 lượt của hôm nay.
    assert sum(diem["reviews"] for diem in body["daily"]) == 2


def test_chua_dang_nhap_tra_401(client: Any) -> None:
    assert client.get("/api/stats").status_code == 401
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd api-service && uv run pytest tests/test_stats_endpoint.py -v
```

Kỳ vọng: FAIL — mọi ca trả 404 vì route chưa tồn tại.

- [ ] **Step 3a: Viết `stats/models.py`**

```python
"""DTO của màn thống kê. KHÔNG có SQLAlchemy entity nào ở đây — tính năng này không tạo bảng.

Dùng `import datetime` rồi annotate `datetime.date` thay vì `from datetime import date`: DTO
có field tên đúng là `date`, và `date: date` tuy chạy được vẫn là thứ khiến người đọc phải
dừng lại kiểm tra xem cái nào là kiểu, cái nào là tên.
"""

from __future__ import annotations

import datetime

from app.common.schema import ApiModel
from app.quiz.models import QuizType


class DailyPoint(ApiModel):
    """Một ô ngày. `reviews = 0` nghĩa là ngày đó không ôn — KHÔNG phải thiếu dữ liệu."""

    date: datetime.date
    reviews: int


class StreakDto(ApiModel):
    """`current` và `longest` là hai con số khác nhau; `lastActiveDate` là None khi chưa ôn
    lần nào."""

    current: int
    longest: int
    last_active_date: datetime.date | None


class TotalsDto(ApiModel):
    """Toàn bộ lịch sử, không giới hạn cửa sổ — đây là màn động lực, con số phải to lên mãi."""

    reviews: int
    learned_words: int
    active_days: int


class RecallDto(ApiModel):
    """Số lượt THÔ theo bốn mức tự chấm. Tỉ lệ nhớ là `1 − again/tổng`, client tự tính — trả
    sẵn cả hai là dựng hai nguồn sự thật cho cùng một con số."""

    again: int
    hard: int
    good: int
    easy: int


class QuizTypeStatsDto(ApiModel):
    """`avgScore` là None với `FILL_BLANK` và `COLLOCATION_CHOICE`: hai loại đó chấm 100 hoặc
    0 nên điểm trung bình chỉ là `correct/attempts` viết lại. None ở đây nghĩa là "loại này
    không có khái niệm điểm", cùng ngữ nghĩa `improvedVersion` trong `AnswerResultDto`."""

    type: QuizType
    attempts: int
    correct: int
    avg_score: int | None


class StatsDto(ApiModel):
    """`daily` LUÔN đúng 91 phần tử; `quiz` LUÔN đúng 3 phần tử theo thứ tự khai báo của
    `QuizType`. Hai bất biến đó là hợp đồng — UI dựa vào để không phải phân nhánh "thiếu dữ
    liệu" ở bốn chỗ."""

    streak: StreakDto
    totals: TotalsDto
    daily: list[DailyPoint]
    recall: RecallDto
    quiz: list[QuizTypeStatsDto]
```

- [ ] **Step 3b: Viết `stats/service.py`**

```python
"""Ghép ba câu truy vấn và hàm streak thành một `StatsDto`."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import get_settings
from app.quiz.models import QuizType
from app.srs import repository as srs_repo
from app.stats import repository as repo
from app.stats.models import (
    DailyPoint,
    QuizTypeStatsDto,
    RecallDto,
    StatsDto,
    StreakDto,
    TotalsDto,
)
from app.stats.streak import tinh_streak

#: Độ dài cửa sổ `daily`. 91 = 13 tuần chẵn. Đổi số này là đổi hợp đồng API — mirror
#: TypeScript và test đều dựa vào "đúng 91 phần tử".
WINDOW_DAYS = 91


def lay_thong_ke(db: Session, user_id: int) -> StatsDto:
    theo_ngay = repo.dem_luot_on_theo_ngay(db, user_id)
    hom_nay = _hom_nay()

    st = tinh_streak([ngay for ngay, _ in theo_ngay], hom_nay)
    so_luot = dict(theo_ngay)
    theo_rating = repo.dem_luot_on_theo_rating(db, user_id)
    theo_loai = repo.thong_ke_quiz_theo_loai(db, user_id)

    return StatsDto(
        streak=StreakDto(
            current=st.current, longest=st.longest, last_active_date=st.last_active
        ),
        totals=TotalsDto(
            reviews=sum(dem for _, dem in theo_ngay),
            # Dùng lại hàm sẵn có của srs thay vì viết lại `count(*) WHERE repetitions >= 1`:
            # hai định nghĩa cho "đã học" sẽ trôi khỏi nhau.
            learned_words=srs_repo.count_learned(db, user_id),
            active_days=len(theo_ngay),
        ),
        daily=[
            DailyPoint(date=ngay, reviews=so_luot.get(ngay, 0)) for ngay in _cua_so(hom_nay)
        ],
        recall=RecallDto(
            again=theo_rating.get("AGAIN", 0),
            hard=theo_rating.get("HARD", 0),
            good=theo_rating.get("GOOD", 0),
            easy=theo_rating.get("EASY", 0),
        ),
        quiz=[_quiz_dto(loai, theo_loai.get(loai.value)) for loai in QuizType],
    )


def _hom_nay() -> date:
    """Hôm nay theo `settings.tz`, KHÔNG theo múi giờ của tiến trình.

    Phải là cùng một múi giờ mà `repository._ngay_dia_phuong()` dùng để gom nhóm. Trên Docker
    hai thứ đó trùng nhau vì container nhận biến `TZ`, nhưng trên Vercel tiến trình chạy giờ
    UTC — dùng `datetime.now().astimezone()` ở đó là lệch 7 tiếng, và ô cuối của heatmap trỏ
    sai ngày trong 7 giờ mỗi ngày.
    """
    return datetime.now(ZoneInfo(get_settings().tz)).date()


def _cua_so(hom_nay: date) -> list[date]:
    """`WINDOW_DAYS` ngày liên tục kết thúc ở hôm nay, tăng dần."""
    return [hom_nay - timedelta(days=WINDOW_DAYS - 1 - i) for i in range(WINDOW_DAYS)]


def _quiz_dto(loai: QuizType, hang: tuple[int, int, float | None] | None) -> QuizTypeStatsDto:
    """Loại chưa làm lần nào vẫn có hàng với số 0 — vắng hàng thì UI phải phân nhánh "chưa
    làm loại này" ở ba chỗ."""
    if hang is None:
        return QuizTypeStatsDto(type=loai, attempts=0, correct=0, avg_score=None)

    attempts, correct, diem_tb = hang
    co_diem = loai is QuizType.FREE_WRITE and diem_tb is not None
    return QuizTypeStatsDto(
        type=loai,
        attempts=attempts,
        correct=correct,
        avg_score=round(diem_tb) if co_diem and diem_tb is not None else None,
    )
```

- [ ] **Step 3c: Viết `stats/router.py`**

```python
"""GET /api/stats"""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.deps import CurrentUserId, Db
from app.stats import service
from app.stats.models import StatsDto

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsDto)
def stats(user_id: CurrentUserId, db: Db) -> StatsDto:
    """Không tham số: cửa sổ thời gian là hằng số phía server (`service.WINDOW_DAYS`).

    Chưa học gì KHÔNG phải lỗi — trả toàn số 0, không bao giờ 404.
    """
    return service.lay_thong_ke(db, user_id)
```

- [ ] **Step 3d: Đăng ký router ở `app/main.py`**

Thêm import cạnh nhóm import router có sẵn (giữ thứ tự alphabet mà ruff/isort yêu cầu):

```python
from app.stats.router import router as stats_router
```

Và thêm dòng cuối trong nhóm `include_router`, ngay sau `quiz_router`:

```python
    app.include_router(quiz_router)
    app.include_router(stats_router)
    return app
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd api-service && uv run pytest tests/test_stats_endpoint.py -v && uv run mypy app && uv run ruff check .
```

Kỳ vọng: 6 passed, mypy `Success`, ruff sạch.

- [ ] **Step 5: Chạy toàn bộ test backend để chắc không vỡ chỗ khác**

```bash
cd api-service && uv run pytest
```

Kỳ vọng: tất cả xanh.

- [ ] **Step 6: Commit**

```bash
git add api-service/app/stats/models.py api-service/app/stats/service.py \
        api-service/app/stats/router.py api-service/app/main.py \
        api-service/tests/test_stats_endpoint.py
git commit -m "feat(stats): endpoint GET /api/stats"
```

---

## Task 4: Chốt chặn cách ly người dùng

Task riêng vì đây là **cổng an toàn của ràng buộc #13**, không phải phần phụ của Task 3. Một reviewer có thể duyệt endpoint mà vẫn từ chối chỗ này.

**Files:**
- Modify: `api-service/tests/test_multi_user_isolation.py` (thêm section `stats` ở cuối file, sau section `quiz`)

**Interfaces:**
- Consumes: `GET /api/stats` (Task 3); fixture `hai_nguoi`, helper `_the_cua`, `_seed_free_write` đã có sẵn trong chính file đó
- Produces: không gì

- [ ] **Step 1: Viết test đỏ**

Thêm vào cuối `api-service/tests/test_multi_user_isolation.py`:

```python
# ── stats ─────────────────────────────────────────────────────────────────────


def test_stats_khong_dem_luot_on_va_quiz_cua_nguoi_khac(
    client: Any, db: Session, hai_nguoi: HaiNguoi
) -> None:
    """Không bảng nào trong ba câu tổng hợp có cột `user_id` — chúng phải join về
    `vocab_entry` mới lọc được. Quên một mệnh đề join là mọi con số của A cộng cả phần của B,
    và không có gì đỏ.

    `learnedWords` là ca dễ lọt nhất: cả hai người đều có đúng một thẻ `repetitions = 3` (do
    fixture `hai_nguoi` dựng), nên thiếu bộ lọc sẽ ra 2 thay vì 1 — một con số trông vẫn rất
    hợp lý.
    """
    the_b = _the_cua(db, hai_nguoi.vocab_b)
    for _ in range(3):
        db.execute(
            text(
                "INSERT INTO review_log (card_id, rating, prev_interval, new_interval) "
                "VALUES (:c, 'GOOD', 0, 1)"
            ),
            {"c": the_b},
        )
    item_b = _seed_free_write(db, hai_nguoi.vocab_b)
    db.execute(
        text(
            "INSERT INTO quiz_attempt (quiz_item_id, user_answer, correct, score) "
            "VALUES (:i, 'câu của B', true, 90)"
        ),
        {"i": item_b},
    )
    db.commit()

    ra = client.get("/api/stats", headers=hai_nguoi.a.headers)
    assert ra.status_code == 200
    a = ra.json()
    assert a["totals"]["reviews"] == 0
    assert a["totals"]["activeDays"] == 0
    assert a["totals"]["learnedWords"] == 1
    assert a["streak"]["current"] == 0
    assert a["streak"]["lastActiveDate"] is None
    assert a["recall"] == {"again": 0, "hard": 0, "good": 0, "easy": 0}
    assert all(hang["attempts"] == 0 for hang in a["quiz"])
    assert sum(diem["reviews"] for diem in a["daily"]) == 0

    b = client.get("/api/stats", headers=hai_nguoi.b.headers).json()
    assert b["totals"]["reviews"] == 3
    assert b["totals"]["learnedWords"] == 1
    assert b["recall"]["good"] == 3
    assert sum(hang["attempts"] for hang in b["quiz"]) == 1
```

- [ ] **Step 2: Chạy test và kiểm nó xanh ngay**

```bash
cd api-service && uv run pytest tests/test_multi_user_isolation.py -v
```

Kỳ vọng: **PASS ngay lần đầu** — Task 2 đã lọc `user_id` đúng.

Test này không theo nhịp đỏ-rồi-xanh vì nó là chốt hồi quy, không phải đặc tả hành vi mới. Muốn thấy nó bắt được lỗi thật thì tạm bỏ dòng `.where(VocabEntry.user_id == user_id)` trong `dem_luot_on_theo_ngay`, chạy lại để thấy nó đỏ, rồi khôi phục.

- [ ] **Step 3: Kiểm nó thực sự bắt được lỗi**

Tạm sửa `app/stats/repository.py`, bỏ `.where(VocabEntry.user_id == user_id)` khỏi `dem_luot_on_theo_ngay`, rồi:

```bash
cd api-service && uv run pytest tests/test_multi_user_isolation.py::test_stats_khong_dem_luot_on_va_quiz_cua_nguoi_khac -v
```

Kỳ vọng: FAIL với `assert 3 == 0`. **Khôi phục lại dòng vừa bỏ** rồi chạy lại cho xanh.

- [ ] **Step 4: Commit**

```bash
git add api-service/tests/test_multi_user_isolation.py
git commit -m "test(stats): chốt chặn cách ly người dùng cho GET /api/stats"
```

---

## Task 5: Nối dây phía extension

**Files:**
- Modify: `extension/src/shared/types.ts` (thêm vào cuối, sau các type quiz)
- Modify: `extension/src/shared/messages.ts`
- Modify: `extension/src/background/api-client.ts`
- Modify: `extension/src/background/service-worker.ts`
- Test: `extension/src/background/api-client.test.ts`, `extension/src/background/service-worker.test.ts`

**Interfaces:**
- Consumes: hợp đồng JSON của `GET /api/stats` (Task 3)
- Produces:
  - `shared/types.ts`: `DailyPoint`, `StreakInfo`, `StatsTotals`, `RecallBreakdown`, `QuizTypeStats`, `StatsDto`
  - `shared/messages.ts`: `GetStatsRequest { type: 'GET_STATS' }`, `ResponseMap['GET_STATS'] = StatsDto`
  - `background/api-client.ts`: `learningStats(): Promise<StatsDto>`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `extension/src/background/api-client.test.ts`, đặt ngay sau ca test của `srsStats`. Dùng `fetchMock` và `jsonResponse` sẵn có trong file — **không dựng khung giả lập thứ hai**:

```ts
  it('learningStats gọi GET /api/stats', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      streak: { current: 0, longest: 0, lastActiveDate: null },
      totals: { reviews: 0, learnedWords: 0, activeDays: 0 },
      daily: [],
      recall: { again: 0, hard: 0, good: 0, easy: 0 },
      quiz: [],
    }));

    await client.learningStats();

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/stats`,
      expect.objectContaining({ method: 'GET' }),
    );
  });
```

Trong `extension/src/background/service-worker.test.ts`, thêm `learningStats` vào object `api` (quanh dòng 12, cạnh `srsStats`):

```ts
  srsStats: vi.fn(),
  learningStats: vi.fn(),
```

Rồi thêm ca test, đặt cạnh ca của `GET_SRS_STATS`. Dùng helper `send()` và biến `refreshBadge` sẵn có:

```ts
  it('GET_STATS gọi learningStats và KHÔNG đụng badge', async () => {
    const STATS = {
      streak: { current: 1, longest: 1, lastActiveDate: '2026-08-11' },
      totals: { reviews: 1, learnedWords: 1, activeDays: 1 },
      daily: [],
      recall: { again: 0, hard: 0, good: 1, easy: 0 },
      quiz: [],
    };
    api.learningStats.mockResolvedValue(STATS);

    const response = await send({ type: 'GET_STATS' });

    expect(api.learningStats).toHaveBeenCalled();
    expect(response).toEqual({ ok: true, data: STATS });
    // Thống kê là màn CHỈ ĐỌC: số thẻ đến hạn không thể đổi vì một lượt xem biểu đồ.
    expect(refreshBadge).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd extension && npm test -- src/background
```

Kỳ vọng: FAIL — `client.learningStats is not a function`.

- [ ] **Step 3a: Thêm mirror vào `shared/types.ts`**

```ts
/** Một ô ngày trong `daily`. `reviews: 0` là "ngày đó không ôn", không phải thiếu dữ liệu. */
export interface DailyPoint {
  date: string;
  reviews: number;
}

export interface StreakInfo {
  current: number;
  longest: number;
  lastActiveDate: string | null;
}

export interface StatsTotals {
  reviews: number;
  learnedWords: number;
  activeDays: number;
}

/** Số lượt THÔ theo 4 mức tự chấm. Tỉ lệ nhớ = `1 − again/tổng`, tính ở chỗ hiển thị. */
export interface RecallBreakdown {
  again: number;
  hard: number;
  good: number;
  easy: number;
}

/**
 * `avgScore` là null với FILL_BLANK và COLLOCATION_CHOICE — hai loại đó chấm 100 hoặc 0 nên
 * điểm trung bình không mang thông tin gì mới. null nghĩa là "loại này không có khái niệm
 * điểm", KHÔNG phải "chưa có dữ liệu".
 */
export interface QuizTypeStats {
  type: QuizType;
  attempts: number;
  correct: number;
  avgScore: number | null;
}

/**
 * Gương của StatsDto phía backend.
 *
 * Hai bất biến mà UI dựa vào: `daily` LUÔN đúng 91 phần tử liên tục kết thúc ở hôm nay (theo
 * múi giờ của server, không phải của trình duyệt), và `quiz` LUÔN đủ 3 phần tử theo thứ tự
 * FILL_BLANK, COLLOCATION_CHOICE, FREE_WRITE.
 */
export interface StatsDto {
  streak: StreakInfo;
  totals: StatsTotals;
  daily: DailyPoint[];
  recall: RecallBreakdown;
  quiz: QuizTypeStats[];
}
```

- [ ] **Step 3b: Thêm message vào `shared/messages.ts`**

Thêm `StatsDto` vào khối `import type { … } from './types'` (giữ thứ tự alphabet đang có), rồi thêm interface cạnh `GetSrsStatsRequest`:

```ts
/**
 * Thống kê tiến độ học. Không tham số: cửa sổ thời gian là hằng số phía server.
 *
 * Tên `GET_STATS` chứ không `GET_LEARNING_STATS` để ngắn, nhưng ĐỪNG nhầm với
 * `GET_SRS_STATS` — cái kia trả số thẻ đến hạn cho badge, cái này trả biểu đồ.
 */
export interface GetStatsRequest {
  type: 'GET_STATS';
}
```

Thêm vào union, ngay sau `GetSrsStatsRequest`:

```ts
  | GetSrsStatsRequest
  | GetStatsRequest
```

Và vào `ResponseMap`, ngay sau `GET_SRS_STATS`:

```ts
  GET_SRS_STATS: SrsStats;
  GET_STATS: StatsDto;
```

- [ ] **Step 3c: Thêm `learningStats()` vào `background/api-client.ts`**

Thêm `StatsDto` vào khối import type, rồi thêm method ngay sau `srsStats`:

```ts
  /**
   * Thống kê tiến độ học. Tên `learningStats` chứ không `stats` để không lẫn với
   * `srsStats` ở ngay trên — cái kia trả số thẻ đến hạn cho badge.
   */
  async learningStats(): Promise<StatsDto> {
    return this.request('/api/stats', { method: 'GET' });
  }
```

- [ ] **Step 3d: Thêm nhánh vào `background/service-worker.ts`**

Ngay sau `case 'GET_SRS_STATS':`:

```ts
    case 'GET_STATS':
      // KHÔNG gọi refreshBadge: đây là màn chỉ đọc, số thẻ đến hạn không thể đổi vì
      // một lượt xem biểu đồ.
      return client.learningStats();
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd extension && npm test -- src/background && npm run build
```

Kỳ vọng: test xanh, `tsc --noEmit` không lỗi, vite build xong.

- [ ] **Step 5: Commit**

```bash
git add extension/src/shared/types.ts extension/src/shared/messages.ts \
        extension/src/background/api-client.ts extension/src/background/service-worker.ts \
        extension/src/background/api-client.test.ts extension/src/background/service-worker.test.ts
git commit -m "feat(stats): nối dây GET_STATS qua service worker"
```

---

## Task 6: `shared/heatmap.ts` — dựng lưới và thang màu

**Files:**
- Create: `extension/src/shared/heatmap.ts`
- Test: `extension/src/shared/heatmap.test.ts`

**Interfaces:**
- Consumes: `DailyPoint` từ `shared/types.ts` (Task 5)
- Produces:
  - `type Level = 0 | 1 | 2 | 3 | 4`
  - `interface Cell { date: string; reviews: number; level: Level }`
  - `type Column = (Cell | null)[]` — đúng 7 phần tử, index 0 = T2 … 6 = CN
  - `levelFor(reviews: number): Level`
  - `parseDay(iso: string): Date`
  - `buildHeatmap(daily: DailyPoint[]): Column[]`

- [ ] **Step 1: Viết test đỏ**

Tạo `extension/src/shared/heatmap.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { buildHeatmap, levelFor, parseDay } from './heatmap';
import type { DailyPoint } from './types';

/** `n` ngày liên tục kết thúc ở `denNgay`, số lượt do `reviewsFor` quyết định. */
function daily(denNgay: string, n: number, reviewsFor: (i: number) => number = () => 0): DailyPoint[] {
  const cuoi = parseDay(denNgay);
  const ra: DailyPoint[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(cuoi.getFullYear(), cuoi.getMonth(), cuoi.getDate() - i);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    ra.push({ date: iso, reviews: reviewsFor(n - 1 - i) });
  }
  return ra;
}

describe('parseDay', () => {
  it('trả đúng ngày địa phương, không lệch vì UTC', () => {
    // Đây là chốt chặn quan trọng nhất của module. `new Date("2026-08-11")` được JS hiểu là
    // NỬA ĐÊM UTC, nên ở múi giờ âm (ví dụ America/New_York) nó lùi về ngày 10 — cả lưới
    // lệch một ô và không có gì báo.
    //
    // Ba assert này đúng ở MỌI múi giờ khi cài đặt đúng, và sai ở múi giờ âm khi cài đặt
    // dùng `new Date(iso)`. Chạy `TZ=America/New_York npm test -- src/shared/heatmap.test.ts`
    // để thấy nó bắt được lỗi.
    const d = parseDay('2026-08-11');
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(7);
    expect(d.getDate()).toBe(11);
  });
});

describe('levelFor', () => {
  it('thang cố định, không co theo giá trị lớn nhất', () => {
    expect(levelFor(0)).toBe(0);
    expect(levelFor(1)).toBe(1);
    expect(levelFor(4)).toBe(1);
    expect(levelFor(5)).toBe(2);
    expect(levelFor(14)).toBe(2);
    expect(levelFor(15)).toBe(3);
    expect(levelFor(29)).toBe(3);
    expect(levelFor(30)).toBe(4);
    expect(levelFor(500)).toBe(4);
  });
});

describe('buildHeatmap', () => {
  it('mảng rỗng cho lưới rỗng', () => {
    expect(buildHeatmap([])).toEqual([]);
  });

  it('mỗi cột đúng 7 ô', () => {
    const cot = buildHeatmap(daily('2026-08-11', 91));
    expect(cot.length).toBeGreaterThanOrEqual(13);
    expect(cot.length).toBeLessThanOrEqual(14);
    for (const c of cot) expect(c).toHaveLength(7);
  });

  it('ô đầu tiên nằm đúng hàng thứ trong tuần của nó', () => {
    // 2026-08-11 là thứ Ba → index 1 (0 = T2). Một ngày duy nhất thì cột đầu có 1 ô đệm
    // ở trên và 5 ô đệm ở dưới.
    const cot = buildHeatmap(daily('2026-08-11', 1));
    expect(cot).toHaveLength(1);
    expect(cot[0][0]).toBeNull();
    expect(cot[0][1]).toEqual({ date: '2026-08-11', reviews: 0, level: 0 });
    expect(cot[0][2]).toBeNull();
  });

  it('giữ nguyên số lượt và gắn đúng mức', () => {
    const cot = buildHeatmap(daily('2026-08-11', 2, (i) => (i === 0 ? 7 : 40)));
    const o = cot.flat().filter((c): c is NonNullable<typeof c> => c !== null);
    expect(o).toEqual([
      { date: '2026-08-10', reviews: 7, level: 2 },
      { date: '2026-08-11', reviews: 40, level: 4 },
    ]);
  });

  it('không mất ô nào khi qua nhiều tuần', () => {
    const cot = buildHeatmap(daily('2026-08-11', 91, () => 1));
    const o = cot.flat().filter((c) => c !== null);
    expect(o).toHaveLength(91);
  });

  it('ô cuối cùng là ngày cuối của daily', () => {
    // Client KHÔNG tự tính "hôm nay" — phần tử cuối của daily chính là hôm nay theo
    // settings.tz của server.
    const cot = buildHeatmap(daily('2026-08-11', 91));
    const o = cot.flat().filter((c) => c !== null);
    expect(o[o.length - 1]?.date).toBe('2026-08-11');
  });
});
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd extension && npm test -- src/shared/heatmap.test.ts
```

Kỳ vọng: FAIL — không resolve được `./heatmap`.

- [ ] **Step 3: Viết implementation tối thiểu**

Tạo `extension/src/shared/heatmap.ts`:

```ts
import type { DailyPoint } from './types';

/** Năm mức đậm nhạt. 0 là ô trống (không ôn ngày đó). */
export type Level = 0 | 1 | 2 | 3 | 4;

export interface Cell {
  date: string;
  reviews: number;
  level: Level;
}

/** Một cột = một tuần, ĐÚNG 7 ô theo thứ tự T2→CN. `null` là ô đệm ngoài khoảng dữ liệu. */
export type Column = (Cell | null)[];

/**
 * Ngưỡng CỐ ĐỊNH, không co theo giá trị lớn nhất của bộ dữ liệu.
 *
 * Thang co theo max làm tuần lười nhất trông y hệt tháng chăm nhất — màu phải mang cùng một
 * nghĩa vào tháng 1 và tháng 6, nếu không biểu đồ chỉ còn là trang trí.
 */
export function levelFor(reviews: number): Level {
  if (reviews <= 0) return 0;
  if (reviews < 5) return 1;
  if (reviews < 15) return 2;
  if (reviews < 30) return 3;
  return 4;
}

/**
 * Parse "YYYY-MM-DD" thành Date GIỜ ĐỊA PHƯƠNG.
 *
 * TUYỆT ĐỐI không dùng `new Date(iso)`: chuỗi chỉ-có-ngày được JS hiểu là nửa đêm UTC, nên ở
 * múi giờ âm `.getDay()` trả về thứ của ngày HÔM TRƯỚC. Cả lưới lệch một ô, không exception,
 * không test nào đỏ trừ test viết riêng cho nó.
 */
export function parseDay(iso: string): Date {
  const [nam, thang, ngay] = iso.split('-').map(Number);
  return new Date(nam, thang - 1, ngay);
}

/** 0 = T2 … 6 = CN. `getDay()` trả 0 cho Chủ nhật nên phải xoay. */
function weekdayIndex(day: Date): number {
  return (day.getDay() + 6) % 7;
}

/**
 * Dựng lưới heatmap từ mảng `daily` của backend.
 *
 * Client KHÔNG tự tính "hôm nay": phần tử cuối của `daily` CHÍNH LÀ hôm nay theo
 * `settings.tz` của server. Gọi `new Date()` ở đây là mở lại đúng cái lỗ múi giờ mà backend
 * vừa bịt bằng `AT TIME ZONE`.
 *
 * 91 ngày cộng ô đệm ra 13 hoặc 14 cột, tuỳ ngày đầu rơi vào thứ mấy.
 */
export function buildHeatmap(daily: DailyPoint[]): Column[] {
  if (daily.length === 0) return [];

  const o: (Cell | null)[] = Array<Cell | null>(weekdayIndex(parseDay(daily[0].date))).fill(null);
  for (const diem of daily) {
    o.push({ date: diem.date, reviews: diem.reviews, level: levelFor(diem.reviews) });
  }
  while (o.length % 7 !== 0) o.push(null);

  const cot: Column[] = [];
  for (let i = 0; i < o.length; i += 7) cot.push(o.slice(i, i + 7));
  return cot;
}
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd extension && npm test -- src/shared/heatmap.test.ts
```

Kỳ vọng: tất cả xanh.

- [ ] **Step 5: Kiểm chốt chặn múi giờ thực sự bắt được lỗi**

```bash
cd extension && TZ=America/New_York npm test -- src/shared/heatmap.test.ts
```

Kỳ vọng: **vẫn xanh** với cài đặt đúng.

Rồi tạm đổi `parseDay` thành `return new Date(iso);` và chạy lại đúng lệnh trên — kỳ vọng `expect(d.getDate()).toBe(11)` **đỏ với giá trị 10**. **Khôi phục lại** rồi chạy lần nữa cho xanh.

Đây là bước bắt buộc, không phải tuỳ chọn: một test không bao giờ đỏ là một test không bảo vệ gì.

- [ ] **Step 6: Commit**

```bash
git add extension/src/shared/heatmap.ts extension/src/shared/heatmap.test.ts
git commit -m "feat(stats): dựng lưới heatmap và thang màu cố định"
```

---

## Task 7: `sidepanel/StatsCharts.tsx` — bốn component vẽ thuần

**Files:**
- Create: `extension/src/sidepanel/StatsCharts.tsx`
- Test: `extension/src/sidepanel/StatsCharts.test.tsx`

**Interfaces:**
- Consumes: `DailyPoint`, `RecallBreakdown`, `QuizTypeStats`, `StreakInfo`, `StatsTotals` (Task 5); `buildHeatmap`, `parseDay` (Task 6)
- Produces: bốn component, **không component nào gọi `sendToBackground`** —
  - `<StatRow streak={StreakInfo} totals={StatsTotals} />`
  - `<DailyBars daily={DailyPoint[]} />` — tự cắt 30 phần tử cuối
  - `<Heatmap daily={DailyPoint[]} />`
  - `<Accuracy recall={RecallBreakdown} quiz={QuizTypeStats[]} />`

- [ ] **Step 1: Viết test đỏ**

Tạo `extension/src/sidepanel/StatsCharts.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Accuracy, DailyBars, Heatmap, StatRow } from './StatsCharts';
import type { DailyPoint, QuizTypeStats } from '../shared/types';

function daily(n: number, reviewsFor: (i: number) => number): DailyPoint[] {
  const cuoi = new Date(2026, 7, 11);
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(cuoi.getFullYear(), cuoi.getMonth(), cuoi.getDate() - (n - 1 - i));
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { date: iso, reviews: reviewsFor(i) };
  });
}

const KHONG_QUIZ: QuizTypeStats[] = [
  { type: 'FILL_BLANK', attempts: 0, correct: 0, avgScore: null },
  { type: 'COLLOCATION_CHOICE', attempts: 0, correct: 0, avgScore: null },
  { type: 'FREE_WRITE', attempts: 0, correct: 0, avgScore: null },
];

describe('StatRow', () => {
  it('hiện đủ bốn con số', () => {
    render(
      <StatRow
        streak={{ current: 5, longest: 23, lastActiveDate: '2026-08-11' }}
        totals={{ reviews: 1284, learnedWords: 312, activeDays: 87 }}
      />,
    );

    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('23')).toBeInTheDocument();
    expect(screen.getByText('1284')).toBeInTheDocument();
    expect(screen.getByText('312')).toBeInTheDocument();
  });
});

describe('DailyBars', () => {
  it('vẽ đúng 30 cột dù nhận vào 91 ngày', () => {
    render(<DailyBars daily={daily(91, () => 3)} />);

    expect(screen.getByRole('img', { name: /30 ngày gần nhất/ })).toBeInTheDocument();
    expect(screen.getAllByTestId('bar')).toHaveLength(30);
  });

  it('không chia cho 0 khi 30 ngày qua không ôn lượt nào', () => {
    // Ca này KHÔNG bị trạng thái rỗng của StatsTab chặn: người dùng có thể có lượt ôn từ
    // 200 ngày trước (totals.reviews > 0) mà 30 ngày qua trắng trơn. `count/max` khi đó là
    // 0/0 = NaN, và `height: NaN%` là cột biến mất — hỏng lặng lẽ, không exception.
    render(<DailyBars daily={daily(30, () => 0)} />);

    const bars = screen.getAllByTestId('bar');
    expect(bars).toHaveLength(30);
    for (const bar of bars) {
      expect(bar.style.height).not.toContain('NaN');
    }
  });
});

describe('Heatmap', () => {
  it('vẽ đủ 91 ô có dữ liệu', () => {
    render(<Heatmap daily={daily(91, () => 2)} />);

    expect(screen.getByRole('img', { name: /91 ngày gần nhất/ })).toBeInTheDocument();
    // Ô đệm không mang testid, nên con số này đúng bằng số ngày có dữ liệu.
    expect(screen.getAllByTestId('cell')).toHaveLength(91);
  });
});

describe('Accuracy', () => {
  it('tỉ lệ nhớ là phần không phải AGAIN', () => {
    render(
      <Accuracy recall={{ again: 20, hard: 20, good: 40, easy: 20 }} quiz={KHONG_QUIZ} />,
    );

    expect(screen.getByText('80%')).toBeInTheDocument();
  });

  it('chưa ôn lượt nào thì hiện gạch ngang, không phải 0% hay NaN', () => {
    render(<Accuracy recall={{ again: 0, hard: 0, good: 0, easy: 0 }} quiz={KHONG_QUIZ} />);

    expect(screen.getByTestId('recall-rate')).toHaveTextContent('—');
  });

  it('loại quiz chưa làm hiện gạch ngang chứ không phải 0%', () => {
    // "Chưa làm" và "làm sai hết" là hai chuyện khác nhau. Hiện 0% cho loại chưa đụng tới
    // là nói dối người học rằng họ đã thử và trượt.
    render(<Accuracy recall={{ again: 0, hard: 0, good: 1, easy: 0 }} quiz={KHONG_QUIZ} />);

    expect(screen.getAllByTestId('quiz-rate')).toHaveLength(3);
    for (const o of screen.getAllByTestId('quiz-rate')) {
      expect(o).toHaveTextContent('—');
    }
  });

  it('điểm trung bình chỉ hiện với Tự viết câu', () => {
    render(
      <Accuracy
        recall={{ again: 0, hard: 0, good: 1, easy: 0 }}
        quiz={[
          { type: 'FILL_BLANK', attempts: 4, correct: 3, avgScore: null },
          { type: 'COLLOCATION_CHOICE', attempts: 0, correct: 0, avgScore: null },
          { type: 'FREE_WRITE', attempts: 5, correct: 3, avgScore: 72 },
        ]}
      />,
    );

    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText(/72/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd extension && npm test -- src/sidepanel/StatsCharts.test.tsx
```

Kỳ vọng: FAIL — không resolve được `./StatsCharts`.

- [ ] **Step 3: Viết implementation tối thiểu**

Tạo `extension/src/sidepanel/StatsCharts.tsx`:

```tsx
import { buildHeatmap, parseDay } from '../shared/heatmap';
import type {
  DailyPoint, QuizTypeStats, RecallBreakdown, StatsTotals, StreakInfo,
} from '../shared/types';

/** Số ngày trên biểu đồ cột. `daily` dài 91 nên đây là phép cắt, không phải request riêng. */
const BAR_DAYS = 30;

const WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];

/** Nhãn khớp với QuizTab để cùng một loại không mang hai tên trong cùng một extension. */
const QUIZ_LABELS: Record<QuizTypeStats['type'], string> = {
  FILL_BLANK: 'Điền từ',
  COLLOCATION_CHOICE: 'Chọn cụm từ',
  FREE_WRITE: 'Tự viết câu',
};

/** "2026-08-11" → "11/08". Dùng `parseDay` chứ không `new Date(iso)` — xem `heatmap.ts`. */
function ddmm(iso: string): string {
  const d = parseDay(iso);
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/**
 * Tỉ lệ phần trăm, hoặc `—` khi mẫu số bằng 0.
 *
 * `—` chứ không `0%`: "chưa làm" và "làm sai hết" là hai chuyện khác nhau, và hiện 0% cho
 * loại chưa đụng tới là nói dối người học rằng họ đã thử và trượt.
 */
function phanTram(tu: number, mau: number): string {
  return mau <= 0 ? '—' : `${Math.round((tu / mau) * 100)}%`;
}

export function StatRow({ streak, totals }: { streak: StreakInfo; totals: StatsTotals }) {
  const o: { nhan: string; so: number }[] = [
    { nhan: 'ngày liên tiếp', so: streak.current },
    { nhan: 'kỷ lục', so: streak.longest },
    { nhan: 'lượt ôn', so: totals.reviews },
    { nhan: 'từ đã học', so: totals.learnedWords },
  ];
  return (
    <div className="stat-row">
      {o.map((item) => (
        <div className="stat-cell" key={item.nhan}>
          <strong>{item.so}</strong>
          <span>{item.nhan}</span>
        </div>
      ))}
    </div>
  );
}

export function DailyBars({ daily }: { daily: DailyPoint[] }) {
  const cua_so = daily.slice(-BAR_DAYS);
  const max = Math.max(0, ...cua_so.map((d) => d.reviews));
  const tong = cua_so.reduce((a, d) => a + d.reviews, 0);

  return (
    <section className="chart">
      <h3>30 ngày gần nhất</h3>
      <div
        className="bars"
        role="img"
        aria-label={`Số lượt ôn 30 ngày gần nhất: tổng ${tong} lượt, cao nhất ${max} lượt trong một ngày`}
      >
        {cua_so.map((d) => (
          <div
            key={d.date}
            className="bar"
            data-testid="bar"
            // max = 0 khi 30 ngày qua không ôn lượt nào. Chia ở đây cho ra NaN, và
            // `height: NaN%` là cột biến mất — cột lùn và cột không có là hai thông tin
            // khác nhau, nên sàn 2% được áp cho mọi trường hợp.
            style={{ height: `${max > 0 ? Math.max(2, (d.reviews / max) * 100) : 2}%` }}
            title={`${ddmm(d.date)}: ${d.reviews} lượt ôn`}
          />
        ))}
      </div>
    </section>
  );
}

export function Heatmap({ daily }: { daily: DailyPoint[] }) {
  const cot = buildHeatmap(daily);
  const co_on = daily.filter((d) => d.reviews > 0).length;
  const cao_nhat = daily.reduce(
    (a, d) => (d.reviews > a.reviews ? d : a),
    { date: '', reviews: 0 },
  );

  // Nhãn nói "91 ngày" chứ không "13 tuần": lưới ra 13 hay 14 cột tuỳ ngày đầu rơi vào thứ
  // mấy, nên "13 tuần" là con số sai vào phần lớn các ngày trong tuần.
  const tom_tat = cao_nhat.reviews > 0
    ? `Lịch ôn 91 ngày gần nhất: ${co_on} ngày có ôn, cao nhất ${cao_nhat.reviews} lượt ngày ${ddmm(cao_nhat.date)}`
    : 'Lịch ôn 91 ngày gần nhất: chưa có ngày nào ôn';

  return (
    <section className="chart">
      <h3>91 ngày gần nhất</h3>
      <div className="heatmap">
        <div className="heatmap-days" aria-hidden="true">
          {WEEKDAYS.map((t) => <span key={t}>{t}</span>)}
        </div>
        {/* Từng ô chỉ có `title`, không `aria-label`: gắn nhãn cho cả 91 ô là bắt trình đọc
            màn hình đọc 91 câu để nói một điều mà hàng số liệu phía trên đã nói rồi. */}
        <div className="heatmap-grid" role="img" aria-label={tom_tat}>
          {cot.map((tuan, i) => (
            <div className="heatmap-col" key={i}>
              {tuan.map((o, j) =>
                o === null
                  ? <div className="cell pad" key={j} />
                  : (
                    <div
                      className={`cell lv${o.level}`}
                      key={j}
                      data-testid="cell"
                      title={`${ddmm(o.date)}: ${o.reviews} lượt ôn`}
                    />
                  ),
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Accuracy({
  recall, quiz,
}: { recall: RecallBreakdown; quiz: QuizTypeStats[] }) {
  const tong_on = recall.again + recall.hard + recall.good + recall.easy;
  const nho = tong_on - recall.again;

  return (
    <section className="chart">
      <h3>Độ chính xác</h3>

      <div className="acc-line">
        <span>Tỉ lệ nhớ khi ôn</span>
        <strong data-testid="recall-rate">{phanTram(nho, tong_on)}</strong>
      </div>
      <div
        className="acc-bar"
        role="img"
        aria-label={`Phân bố mức tự chấm: ${recall.again} quên, ${recall.hard} khó, ${recall.good} nhớ, ${recall.easy} dễ`}
      >
        {(['again', 'hard', 'good', 'easy'] as const).map((muc) => (
          <div
            key={muc}
            className={`seg seg-${muc}`}
            style={{ width: `${tong_on > 0 ? (recall[muc] / tong_on) * 100 : 0}%` }}
          />
        ))}
      </div>

      {quiz.map((hang) => (
        <div className="acc-line" key={hang.type}>
          <span>{QUIZ_LABELS[hang.type]}</span>
          <span className="acc-detail">
            {hang.attempts > 0 && `${hang.correct}/${hang.attempts}`}
            {hang.avgScore !== null && ` · ${hang.avgScore}/100`}
          </span>
          <strong data-testid="quiz-rate">{phanTram(hang.correct, hang.attempts)}</strong>
        </div>
      ))}
    </section>
  );
}
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd extension && npm test -- src/sidepanel/StatsCharts.test.tsx && npm run build
```

Kỳ vọng: tất cả xanh, `tsc --noEmit` sạch.

- [ ] **Step 5: Commit**

```bash
git add extension/src/sidepanel/StatsCharts.tsx extension/src/sidepanel/StatsCharts.test.tsx
git commit -m "feat(stats): bốn component vẽ biểu đồ bằng div + CSS"
```

---

## Task 8: `sidepanel/StatsTab.tsx` — nạp dữ liệu và bốn trạng thái

**Files:**
- Create: `extension/src/sidepanel/StatsTab.tsx`
- Test: `extension/src/sidepanel/StatsTab.test.tsx`

**Interfaces:**
- Consumes: `sendToBackground({ type: 'GET_STATS' })` (Task 5); `StatRow`, `DailyBars`, `Heatmap`, `Accuracy` (Task 7)
- Produces: `export function StatsTab()` — không nhận props, dùng được ngay trong `App.tsx`

- [ ] **Step 1: Viết test đỏ**

Tạo `extension/src/sidepanel/StatsTab.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StatsTab } from './StatsTab';
import type { StatsDto } from '../shared/types';

function stats(patch: Partial<StatsDto> = {}): StatsDto {
  const cuoi = new Date(2026, 7, 11);
  return {
    streak: { current: 5, longest: 23, lastActiveDate: '2026-08-11' },
    totals: { reviews: 1284, learnedWords: 312, activeDays: 87 },
    daily: Array.from({ length: 91 }, (_, i) => {
      const d = new Date(cuoi.getFullYear(), cuoi.getMonth(), cuoi.getDate() - (90 - i));
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      return { date: iso, reviews: 2 };
    }),
    recall: { again: 20, hard: 20, good: 40, easy: 20 },
    quiz: [
      { type: 'FILL_BLANK', attempts: 4, correct: 3, avgScore: null },
      { type: 'COLLOCATION_CHOICE', attempts: 0, correct: 0, avgScore: null },
      { type: 'FREE_WRITE', attempts: 5, correct: 3, avgScore: 72 },
    ],
    ...patch,
  };
}

function mockStats(response: unknown) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) =>
      request.type === 'GET_STATS' ? response : { ok: true, data: null },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

it('hiện bốn khối khi có dữ liệu', async () => {
  mockStats({ ok: true, data: stats() });
  render(<StatsTab />);

  expect(await screen.findByText('ngày liên tiếp')).toBeInTheDocument();
  expect(screen.getByRole('img', { name: /30 ngày gần nhất/ })).toBeInTheDocument();
  expect(screen.getByRole('img', { name: /Lịch ôn 91 ngày gần nhất/ })).toBeInTheDocument();
  expect(screen.getByText('Độ chính xác')).toBeInTheDocument();
});

it('chưa ôn lượt nào thì mời đi ôn, không vẽ bốn khối rỗng', async () => {
  // Tường số 0 và heatmap trắng trơn không nói được gì cho người vừa cài.
  mockStats({
    ok: true,
    data: stats({
      streak: { current: 0, longest: 0, lastActiveDate: null },
      totals: { reviews: 0, learnedWords: 0, activeDays: 0 },
    }),
  });
  render(<StatsTab />);

  expect(await screen.findByText(/Chưa có lượt ôn nào/)).toBeInTheDocument();
  expect(screen.queryByRole('img', { name: /Lịch ôn/ })).not.toBeInTheDocument();
});

it('lỗi retry được thì hiện nút Thử lại và gọi lại', async () => {
  mockStats({ ok: false, error: { code: 'GEMINI_UNAVAILABLE', message: 'Backend đang bận', retryable: true } });
  render(<StatsTab />);

  expect(await screen.findByText('Backend đang bận')).toBeInTheDocument();

  mockStats({ ok: true, data: stats() });
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }));

  expect(await screen.findByText('ngày liên tiếp')).toBeInTheDocument();
});

it('lỗi không retry được thì không có nút Thử lại', async () => {
  mockStats({ ok: false, error: { code: 'UNAUTHORIZED', message: 'Cần đăng nhập', retryable: false } });
  render(<StatsTab />);

  expect(await screen.findByText('Cần đăng nhập')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Thử lại' })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd extension && npm test -- src/sidepanel/StatsTab.test.tsx
```

Kỳ vọng: FAIL — không resolve được `./StatsTab`.

- [ ] **Step 3: Viết implementation tối thiểu**

Tạo `extension/src/sidepanel/StatsTab.tsx`:

```tsx
import { useCallback, useEffect, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { ApiError, StatsDto } from '../shared/types';
import { Accuracy, DailyBars, Heatmap, StatRow } from './StatsCharts';

export function StatsTab() {
  const [data, setData] = useState<StatsDto | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const response = await sendToBackground({ type: 'GET_STATS' });
    if (response.ok) {
      setData(response.data);
      setError(null);
    } else {
      setError(response.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <p className="status">Đang tải…</p>;

  if (error) {
    return (
      <div className="empty">
        <p>{error.message}</p>
        {error.retryable && (
          <button type="button" onClick={() => void load()}>Thử lại</button>
        )}
      </div>
    );
  }

  if (data === null) return null;

  // Chưa ôn lượt nào thì bốn khối chỉ là tường số 0 và một lưới trắng trơn — không nói được
  // gì cho người vừa cài, và tệ hơn là làm màn này trông như đang hỏng.
  if (data.totals.reviews === 0) {
    return (
      <div className="empty">
        <p>Chưa có lượt ôn nào. Ôn vài thẻ ở tab Ôn tập rồi quay lại đây.</p>
      </div>
    );
  }

  return (
    <div className="stats">
      <StatRow streak={data.streak} totals={data.totals} />
      <DailyBars daily={data.daily} />
      <Heatmap daily={data.daily} />
      <Accuracy recall={data.recall} quiz={data.quiz} />
    </div>
  );
}
```

- [ ] **Step 4: Chạy test cho chắc là xanh**

```bash
cd extension && npm test -- src/sidepanel/StatsTab.test.tsx && npm run build
```

Kỳ vọng: 4 passed, build sạch.

- [ ] **Step 5: Commit**

```bash
git add extension/src/sidepanel/StatsTab.tsx extension/src/sidepanel/StatsTab.test.tsx
git commit -m "feat(stats): tab Thống kê với bốn trạng thái"
```

---

## Task 9: Gắn tab thứ 5 và style biểu đồ

**Files:**
- Modify: `extension/src/sidepanel/App.tsx` (type `Tab`, mảng `TABS`, nhánh render)
- Modify: `extension/src/sidepanel/styles.css` (thêm section mới ở cuối; và sửa `.tabs button` quanh dòng 282)
- Test: `extension/src/sidepanel/App.test.tsx`

**Interfaces:**
- Consumes: `StatsTab` (Task 8)
- Produces: không gì — đây là task cuối

- [ ] **Step 1: Viết test đỏ**

Thêm vào `extension/src/sidepanel/App.test.tsx`, trong `describe('App')`. Dùng `mockBackend` sẵn có — nhánh `default` của nó trả `{ ok: true, data: null }` nên `StatsTab` không vẽ gì, và đó là đủ: ca này chỉ chốt rằng tab tồn tại và chuyển được:

```tsx
  it('có tab Thống kê và bấm vào thì chuyển sang đó', async () => {
    mockBackend(null);
    render(<App />);

    const tab = await screen.findByRole('tab', { name: 'Thống kê' });
    await userEvent.click(tab);

    expect(tab).toHaveAttribute('aria-selected', 'true');
  });
```

- [ ] **Step 2: Chạy test cho chắc là đỏ**

```bash
cd extension && npm test -- src/sidepanel/App.test.tsx
```

Kỳ vọng: FAIL — không tìm thấy tab tên `Thống kê`.

- [ ] **Step 3a: Thêm tab vào `App.tsx`**

```tsx
import { StatsTab } from './StatsTab';

type Tab = 'translate' | 'vocab' | 'review' | 'quiz' | 'stats';

const TABS: { id: Tab; label: string }[] = [
  { id: 'translate', label: 'Dịch' },
  { id: 'vocab', label: 'Sổ từ' },
  { id: 'review', label: 'Ôn tập' },
  { id: 'quiz', label: 'Quiz' },
  { id: 'stats', label: 'Thống kê' },
];
```

Và trong `<main>`, sau nhánh `quiz`:

```tsx
        {tab === 'stats' && <StatsTab />}
```

- [ ] **Step 3b: Nới thanh tab cho vừa 5 mục**

Sửa `.tabs button` trong `styles.css` (quanh dòng 282) — chỉ hai thuộc tính:

```css
.tabs button {
  flex: 1;
  margin-bottom: -1px;
  /* 4px thay vì 8px: năm tab ở 400px cho mỗi tab ~72px, mà "Thống kê" ở 13px cần ~58px.
     Padding 8px mỗi bên không còn đủ chỗ và nhãn bị cắt. */
  padding: 13px 4px 11px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: none;
  color: var(--text-2);
  font: inherit;
  font-size: 13px;
  font-weight: 550;
  cursor: pointer;
  transition: color 0.12s;
}
```

- [ ] **Step 3c: Thêm style biểu đồ vào cuối `styles.css`**

```css
/* ============================================================
   Thống kê tiến độ
   Biểu đồ vẽ bằng div + CSS, không thư viện và không SVG (ràng buộc #12).
   Màu lấy từ token sẵn có nên tự hợp dark mode.
   ============================================================ */
.stats { padding-bottom: 16px; }

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-bottom: 18px;
}
.stat-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 12px 4px;
  border-radius: var(--r-card);
  background: var(--surface);
}
.stat-cell strong {
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.stat-cell span {
  color: var(--text-3);
  font-size: 10.5px;
  text-align: center;
  line-height: 1.25;
}

.chart { margin-bottom: 20px; }
.chart h3 {
  margin: 0 0 8px;
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
}

.bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 72px;
  padding: 6px 8px;
  border-radius: var(--r-card);
  background: var(--surface);
}
.bar {
  flex: 1;
  min-height: 2px;
  border-radius: 2px;
  background: var(--accent);
}

.heatmap {
  display: flex;
  gap: 5px;
  padding: 8px;
  border-radius: var(--r-card);
  background: var(--surface);
}
.heatmap-days {
  display: grid;
  grid-template-rows: repeat(7, 1fr);
  gap: 3px;
  color: var(--text-3);
  font-size: 8.5px;
  line-height: 16px;
}
.heatmap-grid { display: flex; flex: 1; gap: 3px; }
.heatmap-col {
  display: grid;
  grid-template-rows: repeat(7, 1fr);
  flex: 1;
  gap: 3px;
}
.cell {
  aspect-ratio: 1;
  border-radius: 2px;
  background: var(--surface-2);
}
/* Ô đệm ngoài khoảng dữ liệu — trong suốt để không đọc nhầm thành "ngày không ôn". */
.cell.pad { background: none; }
.cell.lv0 { background: var(--surface-2); }
.cell.lv1 { background: color-mix(in srgb, var(--accent) 28%, var(--surface-2)); }
.cell.lv2 { background: color-mix(in srgb, var(--accent) 52%, var(--surface-2)); }
.cell.lv3 { background: color-mix(in srgb, var(--accent) 76%, var(--surface-2)); }
.cell.lv4 { background: var(--accent); }

.acc-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 7px 0;
  border-bottom: 1px solid var(--border-2);
  font-size: 13px;
}
.acc-line > span:first-child { flex: 1; min-width: 0; }
.acc-line strong { font-weight: 620; }
.acc-detail {
  color: var(--text-3);
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
}

.acc-bar {
  display: flex;
  overflow: hidden;
  height: 8px;
  margin: 4px 0 10px;
  border-radius: 999px;
  background: var(--surface-2);
}
.seg-again { background: var(--danger); }
.seg-hard  { background: color-mix(in srgb, var(--accent) 40%, var(--surface-2)); }
.seg-good  { background: var(--accent); }
.seg-easy  { background: var(--ok); }
```

- [ ] **Step 4: Chạy toàn bộ test extension**

```bash
cd extension && npm test && npm run build
```

Kỳ vọng: tất cả xanh, build sạch.

- [ ] **Step 5: Đo thanh tab trên bản build thật**

Đây là bước **bắt buộc**, không phải tuỳ chọn — spec ghi rõ con số 72px là suy từ CSS, phải kiểm bằng mắt.

1. `cd extension && npm run build`
2. Vào `chrome://extensions`, bật Developer mode, *Load unpacked* trỏ vào `extension/dist`
3. Mở side panel, đăng nhập, nhìn thanh tab

Kỳ vọng: cả 5 nhãn hiện đủ, không bị cắt, không xuống dòng.

**Nếu "Thống kê" bị cắt hoặc xuống dòng:** đổi nhãn thành `Tiến độ` trong `TABS` của `App.tsx` và trong `App.test.tsx`, rồi chạy lại `npm test`. Đừng giảm font xuống dưới 13px — dưới ngưỡng đó thanh tab khó đọc trên màn hình thường.

- [ ] **Step 6: Xem thật màn Thống kê**

Vẫn trong bản unpacked ở trên: ôn vài thẻ ở tab Ôn tập rồi sang tab Thống kê.

Kỳ vọng: streak hiện 1, biểu đồ cột có đúng một cột cao ở cuối, heatmap có một ô đậm ở vị trí hôm nay, khối Độ chính xác hiện tỉ lệ nhớ và ba hàng quiz (hàng chưa làm hiện `—`).

Kiểm cả dark mode: đổi chế độ tối của hệ điều hành rồi mở lại panel — heatmap và thanh tỉ lệ phải vẫn đọc được.

- [ ] **Step 7: Chạy đủ bốn cổng nghiệm thu**

```bash
cd api-service && uv run pytest && uv run mypy app && uv run ruff check .
```

```bash
cd extension && npm test && npm run build
```

Dán output thật của cả bốn lệnh. Không lệnh nào được bỏ qua.

- [ ] **Step 8: Commit**

```bash
git add extension/src/sidepanel/App.tsx extension/src/sidepanel/App.test.tsx extension/src/sidepanel/styles.css
git commit -m "feat(stats): gắn tab Thống kê vào side panel"
```

---

## Phát hiện ngoài phạm vi

Ghi lại, **không sửa trong plan này**:

`app/srs/service.py:_remaining_new_today` dùng `datetime.combine(date.today(), time.min).astimezone()` — tức múi giờ của **tiến trình**, không phải `settings.tz`. Trên Docker hai thứ trùng nhau vì container nhận biến `TZ` (`docker-compose.yml:62`). **Trên Vercel thì không**: tiến trình chạy giờ UTC còn `settings.tz` vẫn là `Asia/Ho_Chi_Minh`, nên mốc "nửa đêm" lệch 7 tiếng và hạn mức từ mới mỗi ngày reset sai giờ.

`stats/service.py:_hom_nay()` trong plan này cố ý dùng `ZoneInfo(get_settings().tz)` để không lặp lại lỗi đó. Sửa `srs` cho khớp là một thay đổi riêng, có rủi ro riêng (nó đổi hành vi hạn mức từ mới), nên không gộp vào đây.
