"""Bản port của `QuizControllerIT` — tầng HTTP của quiz.

Chỉ giữ những khẳng định mà `test_quiz_service.py` KHÔNG với tới được: mã lỗi validate,
JSON méo, giá trị enum lạ, và hình dạng response thật sự đi ra dây.

Khoá JSON viết camelCase vì đó là thứ extension gửi (`quizItemId`, `vocabIds`).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import GeminiGia, NguoiDungTest


def _tu(db: Session, user_id: int, term: str = "mitigate") -> int:
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry "
                "(term, lemma, lang, pos, meaning_vi, user_id, collocations, examples) "
                "VALUES (:t, :t, 'en', 'verb', :m, :u, '[]'::jsonb, '[]'::jsonb) RETURNING id"
            ),
            {"t": term, "m": f"nghĩa của {term}", "u": user_id},
        ).scalar_one()
    )
    db.commit()
    return vocab_id


def _item(db: Session, vocab_id: int, loai: str, payload: dict[str, Any]) -> int:
    item_id = int(
        db.execute(
            text(
                "INSERT INTO quiz_item (vocab_entry_id, type, payload, prompt_version) "
                "VALUES (:v, :t, CAST(:p AS jsonb), 1) RETURNING id"
            ),
            {"v": vocab_id, "t": loai, "p": json.dumps(payload, ensure_ascii=False)},
        ).scalar_one()
    )
    db.commit()
    return item_id


def _fill_blank(db: Session, vocab_id: int) -> int:
    return _item(
        db,
        vocab_id,
        "FILL_BLANK",
        {
            "question": "Điền từ còn thiếu",
            "sentence": "They must ___ the damage.",
            "answer": "mitigate",
            "hint": "gợi ý",
        },
    )


# ── hình dạng response ────────────────────────────────────────────────────────


def test_response_fill_blank_khong_lo_dap_an_o_bat_ky_dang_nao(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`term` phải là null với FILL_BLANK.

    Đáp án của FILL_BLANK chính là dạng đã bị che của `term` — đa số trường hợp là chuỗi
    giống hệt. Gửi kèm `term` là gửi luôn đáp án, dù `payload.answer` không nằm trong DTO.
    """
    item_id = _fill_blank(db, _tu(db, owner.id))

    resp = client.post(
        "/api/quiz/generate",
        headers=owner.headers,
        json={"vocabIds": [1], "type": "FILL_BLANK"},
    )
    assert resp.status_code == 200
    de = [i for i in resp.json() if i["id"] == item_id]
    assert de, "phải tái dùng đúng item đã gieo"
    item = de[0]

    assert item["term"] is None
    assert item["sentence"] == "They must ___ the damage."
    assert item["options"] is None
    # Đáp án không được lọt ra dưới BẤT KỲ khoá nào.
    assert "mitigate" not in json.dumps(item, ensure_ascii=False)
    # Khoá luôn có mặt kể cả khi null — mirror TypeScript khai `string | null`.
    assert set(item) == {"id", "type", "vocabEntryId", "term", "question", "sentence", "options"}


def test_hinh_dang_collocation_choice(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """options đúng 4, sentence null, term CÓ mặt (khác FILL_BLANK — ở đây term không phải
    đáp án)."""
    vocab_id = _tu(db, owner.id)
    item_id = _item(
        db,
        vocab_id,
        "COLLOCATION_CHOICE",
        {
            "question": "Cụm nào tự nhiên?",
            "options": ["mitigate risk", "mitigate cake", "mitigate blue", "mitigate loud"],
            "correct_index": 0,
        },
    )

    resp = client.post(
        "/api/quiz/generate",
        headers=owner.headers,
        json={"vocabIds": [vocab_id], "type": "COLLOCATION_CHOICE"},
    )
    item = next(i for i in resp.json() if i["id"] == item_id)

    assert item["term"] == "mitigate"
    assert item["sentence"] is None
    assert len(item["options"]) == 4
    # correct_index KHÔNG được đi ra ngoài.
    assert "correctIndex" not in item and "correct_index" not in item


def test_index_trong_options_nhan_duoc_cham_dung(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Câu trả lời là index TRONG CHÍNH mảng `options` panel nhận được.

    Backend xáo lựa chọn lúc LƯU rồi trả nguyên thứ tự đó. Nếu ở đâu đó xáo lại lúc trả
    response, index người dùng gửi lên sẽ trỏ vào một cụm khác — chấm sai mà không có gì đỏ.
    """
    vocab_id = _tu(db, owner.id)
    item_id = _item(
        db,
        vocab_id,
        "COLLOCATION_CHOICE",
        {
            "question": "Cụm nào tự nhiên?",
            "options": ["mitigate cake", "mitigate risk", "mitigate blue", "mitigate loud"],
            "correct_index": 1,
        },
    )
    options = next(
        i
        for i in client.post(
            "/api/quiz/generate",
            headers=owner.headers,
            json={"vocabIds": [vocab_id], "type": "COLLOCATION_CHOICE"},
        ).json()
        if i["id"] == item_id
    )["options"]
    dung = options.index("mitigate risk")

    r_dung = client.post(
        "/api/quiz/answer", headers=owner.headers, json={"quizItemId": item_id, "answer": str(dung)}
    )
    assert r_dung.json()["correct"] is True
    assert r_dung.json()["score"] == 100

    r_sai = client.post(
        "/api/quiz/answer",
        headers=owner.headers,
        json={"quizItemId": item_id, "answer": str((dung + 1) % 4)},
    )
    assert r_sai.json()["correct"] is False
    assert r_sai.json()["score"] == 0


# ── validate request ──────────────────────────────────────────────────────────


def test_thieu_ca_vocab_ids_lan_count_tra_400_neu_dich_danh_hai_field(
    client: Any, owner: NguoiDungTest
) -> None:
    resp = client.post("/api/quiz/generate", headers=owner.headers, json={"type": "FREE_WRITE"})

    assert resp.status_code == 400
    thong_diep = resp.json()["message"]
    assert "vocabIds" in thong_diep and "count" in thong_diep


def test_co_ca_hai_selector_tra_400(client: Any, db: Session, owner: NguoiDungTest) -> None:
    resp = client.post(
        "/api/quiz/generate",
        headers=owner.headers,
        json={"vocabIds": [1], "count": 5, "type": "FREE_WRITE"},
    )
    assert resp.status_code == 400


def test_thieu_type_tra_400(client: Any, owner: NguoiDungTest) -> None:
    resp = client.post("/api/quiz/generate", headers=owner.headers, json={"count": 5})
    assert resp.status_code == 400


def test_count_ngoai_khoang_va_vocab_ids_rong_deu_tra_400(
    client: Any, owner: NguoiDungTest
) -> None:
    for body in (
        {"count": 0, "type": "FREE_WRITE"},
        {"count": 51, "type": "FREE_WRITE"},
        {"vocabIds": [], "type": "FREE_WRITE"},
    ):
        assert (
            client.post("/api/quiz/generate", headers=owner.headers, json=body).status_code == 400
        ), body


def test_type_sai_chinh_ta_tra_400_khong_phai_500(client: Any, owner: NguoiDungTest) -> None:
    """Giá trị enum lạ là lỗi của REQUEST, không phải của server."""
    resp = client.post(
        "/api/quiz/generate", headers=owner.headers, json={"count": 5, "type": "FILLBLANK"}
    )
    assert resp.status_code == 400


def test_json_meo_tra_400_va_khong_doi_lai_noi_dung_nguoi_dung_gui(
    client: Any, owner: NguoiDungTest
) -> None:
    """Thông điệp lỗi đi thẳng ra response. Dội lại nguyên đoạn JSON người dùng gửi là mở
    một đường phản chiếu dữ liệu, và lộ luôn tên class nội bộ."""
    rac = '{"count": 5, "type": "FREE_WRITE", BI_MAT_CUA_TOI'

    resp = client.post(
        "/api/quiz/generate",
        headers={**owner.headers, "Content-Type": "application/json"},
        content=rac,
    )

    assert resp.status_code == 400
    assert "BI_MAT_CUA_TOI" not in resp.text


# ── nộp bài ───────────────────────────────────────────────────────────────────


def test_quiz_item_id_khong_ton_tai_tra_404(client: Any, owner: NguoiDungTest) -> None:
    resp = client.post(
        "/api/quiz/answer", headers=owner.headers, json={"quizItemId": 999999, "answer": "x"}
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"
    assert resp.json()["retryable"] is False


def test_answer_qua_dai_tra_400_text_too_long(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Chặn thủ công để ném TEXT_TOO_LONG (400, đúng ngữ nghĩa) thay vì INTERNAL (500)."""
    item_id = _fill_blank(db, _tu(db, owner.id))

    resp = client.post(
        "/api/quiz/answer",
        headers=owner.headers,
        json={"quizItemId": item_id, "answer": "x" * 1001},
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == "TEXT_TOO_LONG"
    assert "1000" in resp.json()["message"]


def test_tra_loi_sai_fill_blank_thi_feedback_chua_luon_dap_an_dung(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Đây là cách DUY NHẤT người học biết đáp án — `QuizItemDto` cố ý không mang nó."""
    item_id = _fill_blank(db, _tu(db, owner.id))

    body = client.post(
        "/api/quiz/answer", headers=owner.headers, json={"quizItemId": item_id, "answer": "reduce"}
    ).json()

    assert body["correct"] is False
    assert "mitigate" in body["feedback"]
    # FILL_BLANK không có khái niệm câu viết lại.
    assert body["improvedVersion"] is None


def test_nop_answer_rong_cho_fill_blank_van_ghi_lich_su(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Chuỗi rỗng nghĩa là "bỏ qua câu này" — thao tác học tập bình thường.

    Bắt lỗi 400 ở đây vừa làm hỏng trải nghiệm vừa KHÔNG ghi dòng `quiz_attempt` nào, nên
    câu đó lại hiện ở đề sau như chưa từng làm.
    """
    item_id = _fill_blank(db, _tu(db, owner.id))

    resp = client.post(
        "/api/quiz/answer", headers=owner.headers, json={"quizItemId": item_id, "answer": ""}
    )

    assert resp.status_code == 200
    assert resp.json()["score"] == 0
    assert resp.json()["correct"] is False
    so_luot = db.execute(
        text("SELECT count(*) FROM quiz_attempt WHERE quiz_item_id = :i"), {"i": item_id}
    ).scalar_one()
    assert so_luot == 1


def test_nop_answer_rong_cho_free_write_khong_dot_mot_call_gemini_nao(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Bỏ qua câu thì không có gì để chấm. Gọi Gemini ở đây là đốt quota cho một chuỗi rỗng."""
    item_id = _item(db, _tu(db, owner.id), "FREE_WRITE", {"question": "Viết một câu"})

    resp = client.post(
        "/api/quiz/answer", headers=owner.headers, json={"quizItemId": item_id, "answer": ""}
    )

    assert resp.status_code == 200
    assert resp.json()["score"] == 0
    assert gemini.requests == []
