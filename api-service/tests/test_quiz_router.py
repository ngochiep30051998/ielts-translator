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

from tests.conftest import FakeGemini, UserFixture


def _insert_vocab(db: Session, user_id: int, term: str = "mitigate") -> int:
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


def _item(db: Session, vocab_id: int, kind: str, payload: dict[str, Any]) -> int:
    item_id = int(
        db.execute(
            text(
                "INSERT INTO quiz_item (vocab_entry_id, type, payload, prompt_version) "
                "VALUES (:v, :t, CAST(:p AS jsonb), 1) RETURNING id"
            ),
            {"v": vocab_id, "t": kind, "p": json.dumps(payload, ensure_ascii=False)},
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


def test_fill_blank_response_does_not_leak_answer_in_any_form(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """`term` phải là null với FILL_BLANK.

    Đáp án của FILL_BLANK chính là dạng đã bị che của `term` — đa số trường hợp là chuỗi
    giống hệt. Gửi kèm `term` là gửi luôn đáp án, dù `payload.answer` không nằm trong DTO.
    """
    item_id = _fill_blank(db, _insert_vocab(db, owner.id))

    resp = client.post(
        "/api/quiz/generate",
        headers=owner.headers,
        json={"vocabIds": [1], "type": "FILL_BLANK"},
    )
    assert resp.status_code == 200
    matches = [i for i in resp.json() if i["id"] == item_id]
    assert matches, "phải tái dùng đúng item đã gieo"
    item = matches[0]

    assert item["term"] is None
    assert item["sentence"] == "They must ___ the damage."
    assert item["options"] is None
    # Đáp án không được lọt ra dưới BẤT KỲ khoá nào.
    assert "mitigate" not in json.dumps(item, ensure_ascii=False)
    # Khoá luôn có mặt kể cả khi null — mirror TypeScript khai `string | null`.
    assert set(item) == {"id", "type", "vocabEntryId", "term", "question", "sentence", "options"}


def test_collocation_choice_response_shape(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """options đúng 4, sentence null, term CÓ mặt (khác FILL_BLANK — ở đây term không phải
    đáp án)."""
    vocab_id = _insert_vocab(db, owner.id)
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


def test_index_in_received_options_is_graded_correctly(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Câu trả lời là index TRONG CHÍNH mảng `options` panel nhận được.

    Backend xáo lựa chọn lúc LƯU rồi trả nguyên thứ tự đó. Nếu ở đâu đó xáo lại lúc trả
    response, index người dùng gửi lên sẽ trỏ vào một cụm khác — chấm sai mà không có gì đỏ.
    """
    vocab_id = _insert_vocab(db, owner.id)
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
    correct_option_index = options.index("mitigate risk")

    r_correct = client.post(
        "/api/quiz/answer",
        headers=owner.headers,
        json={"quizItemId": item_id, "answer": str(correct_option_index)},
    )
    assert r_correct.json()["correct"] is True
    assert r_correct.json()["score"] == 100

    r_wrong = client.post(
        "/api/quiz/answer",
        headers=owner.headers,
        json={"quizItemId": item_id, "answer": str((correct_option_index + 1) % 4)},
    )
    assert r_wrong.json()["correct"] is False
    assert r_wrong.json()["score"] == 0


# ── validate request ──────────────────────────────────────────────────────────


def test_missing_both_vocab_ids_and_count_returns_400_naming_both_fields(
    client: Any, owner: UserFixture
) -> None:
    resp = client.post("/api/quiz/generate", headers=owner.headers, json={"type": "FREE_WRITE"})

    assert resp.status_code == 400
    message = resp.json()["message"]
    assert "vocabIds" in message and "count" in message


def test_both_selectors_present_returns_400(client: Any, db: Session, owner: UserFixture) -> None:
    resp = client.post(
        "/api/quiz/generate",
        headers=owner.headers,
        json={"vocabIds": [1], "count": 5, "type": "FREE_WRITE"},
    )
    assert resp.status_code == 400


def test_missing_type_returns_400(client: Any, owner: UserFixture) -> None:
    resp = client.post("/api/quiz/generate", headers=owner.headers, json={"count": 5})
    assert resp.status_code == 400


def test_count_out_of_range_and_empty_vocab_ids_both_return_400(
    client: Any, owner: UserFixture
) -> None:
    for body in (
        {"count": 0, "type": "FREE_WRITE"},
        {"count": 51, "type": "FREE_WRITE"},
        {"vocabIds": [], "type": "FREE_WRITE"},
    ):
        assert (
            client.post("/api/quiz/generate", headers=owner.headers, json=body).status_code == 400
        ), body


def test_misspelled_type_returns_400_not_500(client: Any, owner: UserFixture) -> None:
    """Giá trị enum lạ là lỗi của REQUEST, không phải của server."""
    resp = client.post(
        "/api/quiz/generate", headers=owner.headers, json={"count": 5, "type": "FILLBLANK"}
    )
    assert resp.status_code == 400


def test_malformed_json_returns_400_and_does_not_echo_back_user_content(
    client: Any, owner: UserFixture
) -> None:
    """Thông điệp lỗi đi thẳng ra response. Dội lại nguyên đoạn JSON người dùng gửi là mở
    một đường phản chiếu dữ liệu, và lộ luôn tên class nội bộ."""
    malformed_body = '{"count": 5, "type": "FREE_WRITE", BI_MAT_CUA_TOI'

    resp = client.post(
        "/api/quiz/generate",
        headers={**owner.headers, "Content-Type": "application/json"},
        content=malformed_body,
    )

    assert resp.status_code == 400
    assert "BI_MAT_CUA_TOI" not in resp.text


# ── nộp bài ───────────────────────────────────────────────────────────────────


def test_nonexistent_quiz_item_id_returns_404(client: Any, owner: UserFixture) -> None:
    resp = client.post(
        "/api/quiz/answer", headers=owner.headers, json={"quizItemId": 999999, "answer": "x"}
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"
    assert resp.json()["retryable"] is False


def test_answer_too_long_returns_400_text_too_long(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Chặn thủ công để ném TEXT_TOO_LONG (400, đúng ngữ nghĩa) thay vì INTERNAL (500)."""
    item_id = _fill_blank(db, _insert_vocab(db, owner.id))

    resp = client.post(
        "/api/quiz/answer",
        headers=owner.headers,
        json={"quizItemId": item_id, "answer": "x" * 1001},
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == "TEXT_TOO_LONG"
    assert "1000" in resp.json()["message"]


def test_wrong_fill_blank_answer_feedback_always_contains_correct_answer(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Đây là cách DUY NHẤT người học biết đáp án — `QuizItemDto` cố ý không mang nó."""
    item_id = _fill_blank(db, _insert_vocab(db, owner.id))

    body = client.post(
        "/api/quiz/answer", headers=owner.headers, json={"quizItemId": item_id, "answer": "reduce"}
    ).json()

    assert body["correct"] is False
    assert "mitigate" in body["feedback"]
    # FILL_BLANK không có khái niệm câu viết lại.
    assert body["improvedVersion"] is None


def test_submitting_empty_answer_for_fill_blank_still_records_history(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Chuỗi rỗng nghĩa là "bỏ qua câu này" — thao tác học tập bình thường.

    Bắt lỗi 400 ở đây vừa làm hỏng trải nghiệm vừa KHÔNG ghi dòng `quiz_attempt` nào, nên
    câu đó lại hiện ở đề sau như chưa từng làm.
    """
    item_id = _fill_blank(db, _insert_vocab(db, owner.id))

    resp = client.post(
        "/api/quiz/answer", headers=owner.headers, json={"quizItemId": item_id, "answer": ""}
    )

    assert resp.status_code == 200
    assert resp.json()["score"] == 0
    assert resp.json()["correct"] is False
    attempt_count = db.execute(
        text("SELECT count(*) FROM quiz_attempt WHERE quiz_item_id = :i"), {"i": item_id}
    ).scalar_one()
    assert attempt_count == 1


def test_submitting_empty_answer_for_free_write_burns_no_gemini_call(
    client: Any, db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Bỏ qua câu thì không có gì để chấm. Gọi Gemini ở đây là đốt quota cho một chuỗi rỗng."""
    item_id = _item(db, _insert_vocab(db, owner.id), "FREE_WRITE", {"question": "Viết một câu"})

    resp = client.post(
        "/api/quiz/answer", headers=owner.headers, json={"quizItemId": item_id, "answer": ""}
    )

    assert resp.status_code == 200
    assert resp.json()["score"] == 0
    assert gemini.requests == []
