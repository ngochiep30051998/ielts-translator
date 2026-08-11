"""Ba câu truy vấn của màn thống kê.

Test ở tầng repository chứ không chỉ qua HTTP: ca múi giờ dưới đây là lỗi nguy hiểm nhất của
cả tính năng, và nó chỉ nhìn thấy rõ khi so trực tiếp `date` trả về.
"""

from __future__ import annotations

from datetime import date

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
            "VALUES (:c, :r, 0, 1, :t ::timestamptz)"
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
