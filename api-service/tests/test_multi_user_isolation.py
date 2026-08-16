"""Bản port của `MultiUserIsolationIT` — chốt chặn quan trọng nhất của cả hệ thống.

Hai người dùng, dữ liệu TRÙNG TÊN (cả hai cùng lưu từ "mitigate"). Trùng tên là cố ý: nó
bắt được ca truy vấn tìm theo term mà quên lọc user — thứ mà dữ liệu khác nhau sẽ giấu đi
hoàn toàn.

**Luật (ràng buộc #13):** endpoint mới KHÔNG có mặt trong file này là endpoint chưa được
chứng minh an toàn. Quên một mệnh đề `WHERE user_id = ?` không làm gì đỏ cả — nó chỉ lặng
lẽ cho người này đọc dữ liệu người kia.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.srs.models import MASTERED_REPETITIONS
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


@pytest.fixture(params=["bearer", "cookie"], ids=["bearer", "cookie"])
def hai_nguoi(request: pytest.FixtureRequest, db: Session, owner: NguoiDungTest) -> HaiNguoi:
    """Toàn bộ file này chạy HAI lần: một lần qua header Bearer (extension), một lần qua
    cookie phiên (web app).

    Cookie là một đường xác thực mới cho MỌI endpoint chạm dữ liệu học. Ràng buộc #13 nói
    endpoint chưa có mặt ở đây là endpoint chưa được chứng minh an toàn; lập luận đó áp
    dụng y nguyên cho một cách mang danh tính mới. Hai đường hội tụ ở `resolve_user_id` nên
    "chắc là giống nhau" — nhưng "chắc là" chính là thứ file này tồn tại để không phải nói.
    """
    che_do = str(request.param)
    b = replace(tao_nguoi_dung(db, SECOND_EMAIL), che_do=che_do)
    return HaiNguoi(
        a=replace(owner, che_do=che_do),
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


def test_danh_sach_tag_chi_chua_tag_cua_chinh_minh(
    client: Any, db: Session, hai_nguoi: HaiNguoi
) -> None:
    """`GET /api/vocab/tags` bung mảng `tags` rồi gom nhóm. Câu gom nhóm là chỗ dễ rơi mất
    mệnh đề `WHERE user_id = ?` nhất — và rơi thì nó vừa lộ chủ đề người khác đang học, vừa
    thổi phồng `count` của chính mình."""
    db.execute(
        text("UPDATE vocab_entry SET tags = ARRAY['của A'] WHERE id = :i"),
        {"i": hai_nguoi.vocab_a},
    )
    db.execute(
        text("UPDATE vocab_entry SET tags = ARRAY['của A', 'của B'] WHERE id = :i"),
        {"i": hai_nguoi.vocab_b},
    )
    db.commit()

    ra = client.get("/api/vocab/tags", headers=hai_nguoi.a.headers)
    assert ra.status_code == 200
    # 'của A' đếm 1 chứ không 2, và 'của B' không xuất hiện.
    assert ra.json()["tags"] == [{"tag": "của A", "count": 1, "mastered": 0}]
    # `total` là chip "Tất cả" — đếm cả sổ của A, và CHỈ của A.
    assert ra.json()["total"] == 1

    rb = client.get("/api/vocab/tags", headers=hai_nguoi.b.headers)
    assert rb.status_code == 200
    assert sorted(hang["tag"] for hang in rb.json()["tags"]) == ["của A", "của B"]
    assert rb.json()["total"] == 1


def test_mastered_cua_tag_khong_dem_the_on_cua_nguoi_khac(
    client: Any, db: Session, hai_nguoi: HaiNguoi
) -> None:
    """`mastered` là con số ĐẾM MỚI, đọc từ `srs_card.repetitions` — dữ liệu học thuần tuý.

    Nó đi qua một LEFT JOIN mới thêm vào câu gom nhóm tag, và `srs_card` KHÔNG có cột
    `user_id`: chủ sở hữu chỉ suy ra được qua `vocab_entry`. Hai người cùng gắn tag trùng tên
    và cùng có một thẻ đạt ngưỡng, nên rơi mất bộ lọc sẽ ra `mastered = 2` trong khi
    `count = 1` — tỉ lệ thành thạo 200%, và không có gì đỏ.
    """
    for vocab_id in (hai_nguoi.vocab_a, hai_nguoi.vocab_b):
        db.execute(
            text("UPDATE vocab_entry SET tags = ARRAY['Môi trường'] WHERE id = :i"),
            {"i": vocab_id},
        )
        db.execute(
            text("UPDATE srs_card SET repetitions = :r WHERE vocab_entry_id = :i"),
            {"r": MASTERED_REPETITIONS, "i": vocab_id},
        )
    db.commit()

    ra = client.get("/api/vocab/tags", headers=hai_nguoi.a.headers)
    assert ra.status_code == 200
    assert ra.json()["tags"] == [{"tag": "Môi trường", "count": 1, "mastered": 1}]

    rb = client.get("/api/vocab/tags", headers=hai_nguoi.b.headers)
    assert rb.json()["tags"] == [{"tag": "Môi trường", "count": 1, "mastered": 1}]


def test_dem_tu_chua_gan_the_chi_dem_so_tu_cua_minh(
    client: Any, db: Session, hai_nguoi: HaiNguoi
) -> None:
    """`untagged` đi qua một câu đếm KHÁC câu gom nhóm tag ở trên, nên nó cần chốt riêng.

    A gắn thẻ cho từ của mình, B không — nếu câu đếm rơi mất `user_id` thì A vẫn thấy
    "Chưa gắn 1" và bấm vào là một danh sách rỗng không giải thích được.
    """
    db.execute(
        text("UPDATE vocab_entry SET tags = ARRAY['của A'] WHERE id = :i"),
        {"i": hai_nguoi.vocab_a},
    )
    db.commit()

    ra = client.get("/api/vocab/tags", headers=hai_nguoi.a.headers)
    assert ra.status_code == 200
    assert ra.json()["untagged"] == 0

    rb = client.get("/api/vocab/tags", headers=hai_nguoi.b.headers)
    assert rb.json()["untagged"] == 1


def test_loc_chua_gan_the_chi_tra_tu_cua_minh(client: Any, hai_nguoi: HaiNguoi) -> None:
    """`GET /api/vocab?untagged=true` là một đường đọc dữ liệu MỚI, nên nó phải có mặt ở đây.

    Cả hai người đều có đúng một từ chưa gắn thẻ, trùng `term` — thiếu `user_id` trong điều
    kiện lọc thì mỗi người thấy hai dòng "mitigate" và không biết dòng nào của mình.
    """
    ra = client.get("/api/vocab", headers=hai_nguoi.a.headers, params={"untagged": "true"})
    assert ra.status_code == 200
    assert ra.json()["totalElements"] == 1
    assert ra.json()["content"][0]["meaningVi"] == "giảm nhẹ (của A)"

    rb = client.get("/api/vocab", headers=hai_nguoi.b.headers, params={"untagged": "true"})
    assert rb.status_code == 200
    assert rb.json()["totalElements"] == 1
    assert rb.json()["content"][0]["meaningVi"] == "giảm nhẹ (của B)"


def test_sua_tu_cua_nguoi_khac_tra_404_va_du_lieu_khong_doi(
    client: Any, db: Session, hai_nguoi: HaiNguoi
) -> None:
    """404 chứ không 403, và kiểm cả dữ liệu: trả 404 mà vẫn ghi đè là ca tệ nhất — người
    kia mất nghĩa mình tự sửa mà không ai thấy gì."""
    resp = client.patch(
        f"/api/vocab/{hai_nguoi.vocab_b}",
        headers=hai_nguoi.a.headers,
        json={"meaningVi": "bị A ghi đè", "tags": ["A gắn vào"]},
    )
    assert resp.status_code == 404

    db.expire_all()
    hang = db.execute(
        text("SELECT meaning_vi, tags FROM vocab_entry WHERE id = :i"),
        {"i": hai_nguoi.vocab_b},
    ).one()
    assert hang[0] == "giảm nhẹ (của B)"
    assert hang[1] == []


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

    `avgBand` và `introducedLast7` là hai đường đọc MỚI: cái đầu quét thẳng `vocab_entry`,
    cái sau đọc `review_log` qua hai lần join. Band của A và B đặt lệch hẳn nhau (6.0 và 9.0)
    để một câu truy vấn rò sẽ ra 7.5 chứ không phải một con số đúng tình cờ.

    `masteredWords`/`learningWords` là hai câu đếm MỚI nữa. Thẻ của B được đẩy lên đúng
    ngưỡng thuộc còn thẻ của A giữ `repetitions = 3`, nên hai người rơi vào HAI nhóm khác
    nhau: một câu rò sẽ làm A đột nhiên có một từ "đã thuộc" — đúng thứ không thể phát hiện
    bằng mắt.
    """
    the_b = _the_cua(db, hai_nguoi.vocab_b)
    db.execute(
        text("UPDATE vocab_entry SET band_level = '6.0' WHERE id = :i"),
        {"i": hai_nguoi.vocab_a},
    )
    db.execute(
        text("UPDATE vocab_entry SET band_level = '9.0' WHERE id = :i"),
        {"i": hai_nguoi.vocab_b},
    )
    db.execute(
        text("UPDATE srs_card SET repetitions = :r WHERE id = :i"),
        {"r": MASTERED_REPETITIONS, "i": the_b},
    )
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
    assert a["totals"]["masteredWords"] == 0
    assert a["totals"]["learningWords"] == 1
    assert a["totals"]["avgBand"] == 6.0
    assert a["totals"]["introducedLast7"] == 0
    assert a["streak"]["current"] == 0
    assert a["streak"]["lastActiveDate"] is None
    assert a["recall"] == {"again": 0, "hard": 0, "good": 0, "easy": 0}
    assert all(hang["attempts"] == 0 for hang in a["quiz"])
    assert sum(diem["reviews"] for diem in a["daily"]) == 0

    b = client.get("/api/stats", headers=hai_nguoi.b.headers).json()
    assert b["totals"]["reviews"] == 3
    assert b["totals"]["learnedWords"] == 1
    assert b["totals"]["masteredWords"] == 1
    assert b["totals"]["learningWords"] == 0
    assert b["totals"]["avgBand"] == 9.0
    # Ba dòng `prev_interval = 0` ở trên là dữ liệu dựng tay trên CÙNG một thẻ, mà đơn vị của
    # `introducedLast7` là TỪ chứ không phải lượt — nên B thấy 1, không phải 3. Điều cần chốt
    # ở đây vẫn là A không thấy dòng nào.
    assert b["totals"]["introducedLast7"] == 1
    assert b["recall"]["good"] == 3
    assert sum(hang["attempts"] for hang in b["quiz"]) == 1
