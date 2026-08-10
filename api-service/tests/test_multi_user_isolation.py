"""Bản port của `MultiUserIsolationIT` — chốt chặn quan trọng nhất của cả hệ thống.

Hai người dùng, dữ liệu TRÙNG TÊN (cả hai cùng lưu từ "mitigate"). Trùng tên là cố ý: nó
bắt được ca truy vấn tìm theo term mà quên lọc user — thứ mà dữ liệu khác nhau sẽ giấu đi
hoàn toàn.

**Luật (ràng buộc #13):** endpoint mới KHÔNG có mặt trong file này là endpoint chưa được
chứng minh an toàn. Quên một mệnh đề `WHERE user_id = ?` không làm gì đỏ cả — nó chỉ lặng
lẽ cho người này đọc dữ liệu người kia.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import SECOND_EMAIL, GeminiGia, NguoiDungTest, tao_nguoi_dung


@dataclass
class HaiNguoi:
    a: NguoiDungTest
    b: NguoiDungTest
    vocab_a: int
    vocab_b: int


def _seed_tu(db: Session, user_id: int, term: str, nghia: str) -> int:
    """Một từ đã ôn — đủ điều kiện vào cả hàng đợi SRS lẫn danh sách ứng viên quiz."""
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id) "
                "VALUES (:t, :t, 'en', 'verb', :m, :u) RETURNING id"
            ),
            {"t": term, "m": nghia, "u": user_id},
        ).scalar_one()
    )
    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses) "
            "VALUES (:v, CURRENT_DATE, 'REVIEW', 3, 1)"
        ),
        {"v": vocab_id},
    )
    db.commit()
    return vocab_id


@pytest.fixture
def hai_nguoi(db: Session, owner: NguoiDungTest) -> HaiNguoi:
    b = tao_nguoi_dung(db, SECOND_EMAIL)
    return HaiNguoi(
        a=owner,
        b=b,
        vocab_a=_seed_tu(db, owner.id, "mitigate", "giảm nhẹ (của A)"),
        vocab_b=_seed_tu(db, b.id, "mitigate", "giảm nhẹ (của B)"),
    )


def _the_cua(db: Session, vocab_id: int) -> int:
    return int(
        db.execute(
            text("SELECT id FROM srs_card WHERE vocab_entry_id = :v"), {"v": vocab_id}
        ).scalar_one()
    )


def _seed_free_write(db: Session, vocab_id: int) -> int:
    item_id = int(
        db.execute(
            text(
                "INSERT INTO quiz_item (vocab_entry_id, type, payload, prompt_version) "
                "VALUES (:v, 'FREE_WRITE', '{\"question\":\"Viết một câu\"}'::jsonb, 1) "
                "RETURNING id"
            ),
            {"v": vocab_id},
        ).scalar_one()
    )
    db.commit()
    return item_id


# ── vocabulary ────────────────────────────────────────────────────────────────


def test_danh_sach_vocab_chi_tra_so_tu_cua_chinh_minh(client: Any, hai_nguoi: HaiNguoi) -> None:
    """Kể cả `totalElements`.

    Con số đó đến từ một câu đếm RIÊNG. Quên `user_id` ở đó thì danh sách đúng nhưng con số
    lộ kích thước sổ từ của người khác.
    """
    ra = client.get("/api/vocab", headers=hai_nguoi.a.headers)
    assert ra.status_code == 200
    assert ra.json()["totalElements"] == 1
    assert ra.json()["content"][0]["meaningVi"] == "giảm nhẹ (của A)"

    rb = client.get("/api/vocab", headers=hai_nguoi.b.headers)
    assert rb.status_code == 200
    assert rb.json()["totalElements"] == 1
    assert rb.json()["content"][0]["meaningVi"] == "giảm nhẹ (của B)"


def test_doc_tu_cua_nguoi_khac_tra_404_khong_phai_403(
    client: Any, hai_nguoi: HaiNguoi
) -> None:
    """404 chứ không 403: 403 xác nhận "id này có tồn tại", tức là một kênh dò id."""
    resp = client.get(f"/api/vocab/{hai_nguoi.vocab_b}", headers=hai_nguoi.a.headers)
    assert resp.status_code == 404


def test_xoa_tu_cua_nguoi_khac_tra_404_va_hang_do_van_con(
    client: Any, db: Session, hai_nguoi: HaiNguoi
) -> None:
    resp = client.delete(f"/api/vocab/{hai_nguoi.vocab_b}", headers=hai_nguoi.a.headers)
    assert resp.status_code == 404

    # Kiểm cả status LẪN dữ liệu: trả 404 mà vẫn xoá là ca tệ nhất và im lặng nhất.
    con_lai = db.execute(
        text("SELECT count(*) FROM vocab_entry WHERE id = :v"), {"v": hai_nguoi.vocab_b}
    ).scalar_one()
    assert con_lai == 1


def test_export_csv_chi_chua_tu_cua_minh(client: Any, hai_nguoi: HaiNguoi) -> None:
    resp = client.get("/api/vocab/export.csv", headers=hai_nguoi.a.headers)

    assert resp.status_code == 200
    assert "giảm nhẹ (của A)" in resp.text
    assert "giảm nhẹ (của B)" not in resp.text


def test_hai_nguoi_cung_luu_mot_tu_deu_duoc(hai_nguoi: HaiNguoi) -> None:
    """Chính là ràng buộc mà V6 đổi. Nếu ai đó khôi phục `uq_vocab_term_pos` toàn cục thì
    fixture ở trên đã nổ trước khi tới đây."""
    assert hai_nguoi.vocab_a != hai_nguoi.vocab_b


# ── srs ───────────────────────────────────────────────────────────────────────


def test_srs_due_va_stats_chi_dem_the_cua_minh(client: Any, hai_nguoi: HaiNguoi) -> None:
    due = client.get("/api/srs/due", headers=hai_nguoi.a.headers)
    assert due.status_code == 200
    assert len(due.json()) == 1

    stats = client.get("/api/srs/stats", headers=hai_nguoi.a.headers)
    assert stats.status_code == 200
    assert stats.json()["dueCount"] == 1


def test_on_the_cua_nguoi_khac_tra_404_va_lich_khong_doi(
    client: Any, db: Session, hai_nguoi: HaiNguoi
) -> None:
    the_b = _the_cua(db, hai_nguoi.vocab_b)
    truoc = db.execute(
        text("SELECT due_date::text FROM srs_card WHERE id = :c"), {"c": the_b}
    ).scalar_one()

    resp = client.post(
        "/api/srs/review",
        headers=hai_nguoi.a.headers,
        json={"cardId": the_b, "rating": "GOOD"},
    )
    assert resp.status_code == 404

    db.expire_all()
    sau = db.execute(
        text("SELECT due_date::text FROM srs_card WHERE id = :c"), {"c": the_b}
    ).scalar_one()
    assert sau == truoc


# ── quiz ──────────────────────────────────────────────────────────────────────


def test_generate_voi_vocab_ids_cua_nguoi_khac_khong_sinh_de_nao(
    client: Any, gemini: GeminiGia, hai_nguoi: HaiNguoi
) -> None:
    """`vocabIds` đến THẲNG từ client. Đây là lỗ IDOR rõ nhất của cả hệ thống: đề sinh ra sẽ
    chứa term và câu ví dụ lấy từ sổ từ của người khác."""
    resp = client.post(
        "/api/quiz/generate",
        headers=hai_nguoi.a.headers,
        json={"vocabIds": [hai_nguoi.vocab_b], "type": "FREE_WRITE"},
    )

    assert resp.status_code == 200
    assert resp.json() == []
    # Và không đốt quota Gemini cho một request đang cố đọc dữ liệu người khác.
    assert gemini.requests == []


def test_tra_loi_item_cua_nguoi_khac_tra_404(
    client: Any, db: Session, gemini: GeminiGia, hai_nguoi: HaiNguoi
) -> None:
    item_b = _seed_free_write(db, hai_nguoi.vocab_b)

    resp = client.post(
        "/api/quiz/answer",
        headers=hai_nguoi.a.headers,
        json={"quizItemId": item_b, "answer": ""},
    )
    assert resp.status_code == 404

    so_luot = db.execute(
        text("SELECT count(*) FROM quiz_attempt WHERE quiz_item_id = :i"), {"i": item_b}
    ).scalar_one()
    assert so_luot == 0


def test_giai_thich_item_cua_nguoi_khac_tra_404_va_khong_goi_gemini(
    client: Any, db: Session, gemini: GeminiGia, hai_nguoi: HaiNguoi
) -> None:
    item_b = _seed_free_write(db, hai_nguoi.vocab_b)
    # B đã trả lời rồi, nên 404 ở đây KHÔNG thể do "chưa có lượt làm".
    db.execute(
        text(
            "INSERT INTO quiz_attempt (quiz_item_id, user_answer, correct, score) "
            "VALUES (:i, 'we mitigate it', true, 90)"
        ),
        {"i": item_b},
    )
    db.commit()

    resp = client.post(
        "/api/quiz/explain", headers=hai_nguoi.a.headers, json={"quizItemId": item_b}
    )

    assert resp.status_code == 404
    # /explain TIẾT LỘ ĐÁP ÁN — rò ở đây vừa là rò dữ liệu vừa là đốt quota của B.
    assert gemini.requests == []


# ── ngoại lệ có chủ ý ─────────────────────────────────────────────────────────


def test_lookup_cache_co_y_dung_chung(
    client: Any, gemini: GeminiGia, hai_nguoi: HaiNguoi
) -> None:
    """B ăn cache của A và đó là TÍNH NĂNG.

    Bất biến NGƯỢC CHIỀU mọi test còn lại trong file này, nên phải viết ra: bản dịch của một
    chuỗi công khai không phải dữ liệu cá nhân, và dùng chung là phần tiết kiệm quota Gemini
    lớn nhất của hệ thống. Ai đó "sửa cho nhất quán" bằng cách thêm `user_id` vào
    `lookup_cache` sẽ làm test này đỏ (ràng buộc #14).
    """
    gemini.tra_json({"term": "mitigate", "meaning_vi": "giảm nhẹ", "pos": "verb"})

    ra = client.post("/api/translate", headers=hai_nguoi.a.headers, json={"text": "mitigate"})
    assert ra.status_code == 200, ra.text
    assert ra.json()["cached"] is False

    rb = client.post("/api/translate", headers=hai_nguoi.b.headers, json={"text": "mitigate"})
    assert rb.status_code == 200, rb.text
    assert rb.json()["cached"] is True
    # Đúng MỘT lượt gọi Gemini cho hai người dùng.
    assert len(gemini.requests) == 1
