"""Bản port của `SrsControllerIT` — hợp đồng HTTP của màn ôn tập.

Khoá JSON và tên tham số query cố ý viết camelCase: đó là thứ extension thật sự gửi
(`newLimit`, `cardId`). Test bằng snake_case sẽ xanh nhờ `populate_by_name` mà vẫn để lọt
một backend không nói chuyện được với extension.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import NguoiDungTest


def _seed(
    db: Session, user_id: int, term: str, *, den_han: bool = True, state: str = "REVIEW"
) -> tuple[int, int]:
    """Trả (vocab_id, card_id)."""
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry "
                "(term, lemma, lang, pos, ipa, meaning_vi, definition_en, cefr, band_level, "
                " user_id, collocations, examples) "
                "VALUES (:t, :t, 'en', 'verb', '/ˈmɪtɪɡeɪt/', :m, 'to make less severe', "
                "        'C1', '7.0', :u, '[]'::jsonb, '[]'::jsonb) RETURNING id"
            ),
            {"t": term, "m": f"nghĩa của {term}", "u": user_id},
        ).scalar_one()
    )
    card_id = int(
        db.execute(
            text(
                "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses, "
                "                      ease_factor, interval_days) "
                "VALUES (:v, CURRENT_DATE + :offset, :s, 3, 1, 2.5, 7) RETURNING id"
            ),
            {"v": vocab_id, "offset": 0 if den_han else 5, "s": state},
        ).scalar_one()
    )
    db.commit()
    return vocab_id, card_id


def test_due_tra_the_kem_du_lieu_vocab_da_gop_san(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Gộp sẵn để side panel chỉ phải gọi MỘT lượt cho cả xấp thẻ — thay vì một lượt cho
    hàng đợi rồi N lượt tra từng từ."""
    _seed(db, owner.id, "mitigate")

    resp = client.get("/api/srs/due", headers=owner.headers)

    assert resp.status_code == 200, resp.text
    the = resp.json()[0]
    assert the["term"] == "mitigate"
    assert the["meaningVi"] == "nghĩa của mitigate"
    assert the["definitionEn"] == "to make less severe"
    assert the["ipa"] == "/ˈmɪtɪɡeɪt/"
    assert the["cefr"] == "C1"
    assert the["state"] == "REVIEW"
    assert "dueDate" in the and "vocabEntryId" in the


def test_stats_tra_ba_con_so(client: Any, db: Session, owner: NguoiDungTest) -> None:
    _seed(db, owner.id, "mitigate")
    _seed(db, owner.id, "resilient", state="NEW")

    resp = client.get("/api/srs/stats", headers=owner.headers)

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"dueCount", "newCount", "learnedCount"}
    assert body["newCount"] == 1


def test_review_tra_lich_ke_tiep(client: Any, db: Session, owner: NguoiDungTest) -> None:
    _, card_id = _seed(db, owner.id, "mitigate")

    resp = client.post(
        "/api/srs/review", headers=owner.headers, json={"cardId": card_id, "rating": "GOOD"}
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"nextDueDate", "intervalDays", "easeFactor"}
    assert body["intervalDays"] >= 1
    assert body["easeFactor"] == 2.5  # GOOD không đổi EF


def test_review_the_la_tra_404_dung_hinh_dang_loi_chung(
    client: Any, owner: NguoiDungTest
) -> None:
    resp = client.post(
        "/api/srs/review", headers=owner.headers, json={"cardId": 999999, "rating": "GOOD"}
    )

    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "NOT_FOUND"
    assert body["retryable"] is False


def test_review_thieu_rating_tra_400(client: Any, db: Session, owner: NguoiDungTest) -> None:
    _, card_id = _seed(db, owner.id, "mitigate")

    resp = client.post("/api/srs/review", headers=owner.headers, json={"cardId": card_id})

    assert resp.status_code == 400
    assert resp.json()["code"] == "INTERNAL"


def test_rating_sai_chinh_ta_tra_400_khong_phai_500(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Giá trị enum lạ là lỗi của REQUEST. Trả 500 ở đây là đổ lỗi cho server và làm UI hiện
    "lỗi không xác định" thay vì nói request sai."""
    _, card_id = _seed(db, owner.id, "mitigate")

    resp = client.post(
        "/api/srs/review", headers=owner.headers, json={"cardId": card_id, "rating": "GOODD"}
    )

    assert resp.status_code == 400


def test_card_dto_co_hai_mang_moi_nhu_rong_khi_chua_sinh(
    client: Any, db: Session, gemini: Any, owner: NguoiDungTest
) -> None:
    """Rỗng nghĩa là mồi nhử chưa sinh kịp — panel tự bù bằng thẻ khác trong hàng đợi chứ
    KHÔNG coi đó là lỗi. Thiếu hẳn khoá thì panel đọc `undefined` và vỡ."""
    _seed(db, owner.id, "mitigate")

    the = client.get("/api/srs/due", headers=owner.headers).json()[0]

    assert the["viDistractors"] == []
    assert the["enDistractors"] == []


def test_the_chua_den_han_khong_nam_trong_hang_doi(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    _seed(db, owner.id, "mitigate", den_han=False)

    assert client.get("/api/srs/due", headers=owner.headers).json() == []


def test_new_limit_doc_dung_ten_query_camel_case(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Hợp đồng cũ của Spring lấy tên tham số từ bytecode nên query string là `newLimit`.

    Nếu backend chỉ nhận `new_limit` thì extension gửi `newLimit` sẽ rơi về mặc định — không
    lỗi, không test nào đỏ, chỉ là hạn mức từ mới của người dùng bị bỏ qua.

    Khối chứng minh camelCase là `newLimit=2`: bỏ qua tham số thì mặc định 30 cho ra 3 thẻ
    chứ không phải 2. Khối `newLimit=0` giờ chốt ngữ nghĩa MỚI — `0` nghĩa là không giới hạn,
    không phải "cấm học từ mới" như trước.
    """
    for i in range(3):
        _seed(db, owner.id, f"tu-moi-{i}", state="NEW")

    khong_gioi_han = client.get(
        "/api/srs/due", params={"newLimit": 0}, headers=owner.headers
    )
    assert khong_gioi_han.status_code == 200
    assert len(khong_gioi_han.json()) == 3

    cho_hai = client.get("/api/srs/due", params={"newLimit": 2}, headers=owner.headers)
    assert len(cho_hai.json()) == 2
