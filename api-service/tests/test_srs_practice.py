"""Chế độ luyện thêm — bất biến trung tâm là `srs_card` KHÔNG ĐỔI.

Mọi thứ khác trong tính năng này hỏng thì còn sửa được; một cột trong `srs_card` bị đổi sai
là lịch học của người dùng hỏng vĩnh viễn và không khôi phục được.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import UserFixture


def _seed_card(
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


def _snapshot_card(db: Session, card_id: int) -> tuple[Any, ...]:
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


def test_practicing_five_times_changes_no_column_of_the_card(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Bất biến trung tâm của cả spec.

    Năm lượt chứ không một: nếu ai đó vô ý gọi `next_schedule` trong `practice()`, một lượt
    có thể trùng giá trị cũ do làm tròn, năm lượt thì không."""
    card_id = _seed_card(db, owner.id, "mitigate")
    before = _snapshot_card(db, card_id)

    for rating in ("AGAIN", "HARD", "GOOD", "EASY", "GOOD"):
        resp = client.post(
            "/api/srs/practice",
            headers=owner.headers,
            json={"cardId": card_id, "rating": rating},
        )
        assert resp.status_code == 204

    assert _snapshot_card(db, card_id) == before


def test_practice_writes_exactly_one_row_with_mode_practice(
    client: Any, db: Session, owner: UserFixture
) -> None:
    card_id = _seed_card(db, owner.id, "mitigate", interval_days=6)

    client.post(
        "/api/srs/practice", headers=owner.headers, json={"cardId": card_id, "rating": "GOOD"}
    )

    mode, prev, new_interval = db.execute(
        text("SELECT mode, prev_interval, new_interval FROM review_log WHERE card_id = :c"),
        {"c": card_id},
    ).one()
    assert mode == "PRACTICE"
    # Không phải số giả: lịch thật sự không đổi nên hai con số thật sự bằng nhau.
    assert (prev, new_interval) == (6, 6)


def test_practice_queue_excludes_new_cards(client: Any, db: Session, owner: UserFixture) -> None:
    """Lượt đầu đời của một thẻ phải đi đường có lịch, nếu không nó mắc kẹt ở NEW vĩnh viễn."""
    _seed_card(db, owner.id, "mitigate", repetitions=2)
    _seed_card(db, owner.id, "brandnew", repetitions=0, interval_days=0)

    response = client.get("/api/srs/practice", headers=owner.headers)

    assert response.status_code == 200
    assert [c["term"] for c in response.json()] == ["mitigate"]


def test_practice_queue_includes_just_forgotten_cards(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Thẻ RELEARNING (vừa bấm "Lại") phải có mặt trong hàng luyện.

    Trạng thái đúng như `next_schedule()` sinh ra cho rating AGAIN: `repetitions = 0`,
    `state = RELEARNING`, `interval_days = 1`, `lapses = 1`. Thẻ này đã học rồi — nó chỉ vừa
    bị quên — nên lọc theo `repetitions >= 1` loại nhầm đúng tập thẻ mà tính năng luyện thêm
    sinh ra để phục vụ.
    """
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id) "
                "VALUES ('forgotten','forgotten','en','verb','vừa quên',:u) RETURNING id"
            ),
            {"u": owner.id},
        ).scalar_one()
    )
    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, "
            "interval_days, lapses, ease_factor) "
            "VALUES (:v, CURRENT_DATE + 1, 'RELEARNING', 0, 1, 1, 2.5)"
        ),
        {"v": vocab_id},
    )
    db.commit()

    response = client.get("/api/srs/practice", headers=owner.headers)

    assert response.status_code == 200
    assert [c["term"] for c in response.json()] == ["forgotten"]


def test_practice_queue_still_contains_due_cards(
    client: Any, db: Session, owner: UserFixture
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


def test_practicing_nonexistent_card_returns_404(client: Any, owner: UserFixture) -> None:
    resp = client.post(
        "/api/srs/practice", headers=owner.headers, json={"cardId": 999999, "rating": "GOOD"}
    )
    assert resp.status_code == 404


def test_not_logged_in_returns_401(client: Any) -> None:
    assert client.get("/api/srs/practice").status_code == 401
    assert client.post("/api/srs/practice", json={"cardId": 1, "rating": "GOOD"}).status_code == 401
