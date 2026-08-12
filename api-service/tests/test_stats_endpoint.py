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
