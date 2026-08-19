"""Bản port của `SrsCardCreatorIT`.

Bên Java đây là một `@EventListener` của `VocabEntrySavedEvent`; ở đây là một lời gọi hàm
thẳng từ `vocabulary.service.save`. Test đi qua ĐƯỜNG HTTP thật chứ không gọi hàm trực
tiếp — thứ cần chứng minh là "lưu một từ thì thẻ ôn có mặt", không phải "hàm này chạy đúng
khi được gọi".
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import UserFixture

BODY = {
    "term": "mitigate",
    "lemma": "mitigate",
    "lang": "en",
    "pos": "verb",
    "meaningVi": "giảm nhẹ",
}


def _cards_of_term(db: Session, term: str) -> list[Any]:
    return list(
        db.execute(
            text(
                "SELECT c.state, c.due_date, c.repetitions FROM srs_card c "
                "JOIN vocab_entry v ON v.id = c.vocab_entry_id WHERE v.term = :t"
            ),
            {"t": term},
        )
    )


def test_saving_single_word_creates_review_card_immediately(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Due hôm nay, state NEW.

    Chạy đồng bộ trong cùng transaction với lệnh lưu, nên từ và thẻ hoặc cùng có hoặc cùng
    không — không có trạng thái từ đã lưu mà thiếu thẻ.
    """
    assert client.post("/api/vocab", headers=owner.headers, json=BODY).status_code == 200

    rows = _cards_of_term(db, "mitigate")
    assert len(rows) == 1
    state, due_date, repetitions = rows[0]
    assert state == "NEW"
    assert repetitions == 0
    today = db.execute(text("SELECT CURRENT_DATE")).scalar_one()
    assert due_date == today


def test_saving_whole_sentence_does_not_create_card(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """`pos = 'phrase'` là câu đầy đủ do service worker đặt khi mode = SENTENCE. Flashcard
    một câu dài là vô nghĩa, nên không tạo thẻ."""
    body = {**BODY, "term": "Governments must act now.", "pos": "phrase"}

    assert client.post("/api/vocab", headers=owner.headers, json=body).status_code == 200

    assert _cards_of_term(db, "Governments must act now.") == []


def test_resaving_existing_word_does_not_create_second_card(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Lưu lại một từ cũ KHÔNG được đặt lại lịch ôn của nó từ đầu.

    Nhánh `alreadyExists` phải return sớm trước khi chạm tới việc tạo thẻ — nếu không, mỗi
    lần bôi đen lại một từ đã học là lịch ôn của nó lùi về ngày đầu tiên.
    """
    assert client.post("/api/vocab", headers=owner.headers, json=BODY).status_code == 200
    second_response = client.post("/api/vocab", headers=owner.headers, json=BODY)

    assert second_response.status_code == 200
    assert second_response.json()["alreadyExists"] is True
    assert len(_cards_of_term(db, "mitigate")) == 1


def test_empty_pos_still_creates_card(client: Any, db: Session, owner: UserFixture) -> None:
    """Chỉ đúng chuỗi `"phrase"` mới bị bỏ qua. `pos` rỗng là từ chưa phân loại, vẫn học được."""
    body = {**BODY, "term": "resilient", "pos": ""}

    assert client.post("/api/vocab", headers=owner.headers, json=body).status_code == 200

    assert len(_cards_of_term(db, "resilient")) == 1
