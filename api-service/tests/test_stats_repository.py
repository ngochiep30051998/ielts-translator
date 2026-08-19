"""Ba câu truy vấn của màn thống kê.

Test ở tầng repository chứ không chỉ qua HTTP: ca múi giờ dưới đây là lỗi nguy hiểm nhất của
cả tính năng, và nó chỉ nhìn thấy rõ khi so trực tiếp `date` trả về.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.stats import repository as repo
from tests.conftest import SECOND_EMAIL, UserFixture, create_user


def _seed_card(db: Session, user_id: int, term: str) -> int:
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


def _seed_review(db: Session, card_id: int, rating: str, reviewed_at_text: str) -> None:
    """`luc` là timestamptz dạng chuỗi, ví dụ '2026-08-11 18:00:00+00'."""
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, reviewed_at) "
            "VALUES (:c, :r, 0, 1, :t ::timestamptz)"
        ),
        {"c": card_id, "r": rating, "t": reviewed_at_text},
    )


def test_review_at_1am_vietnam_time_belongs_to_that_day(
    db: Session, owner: UserFixture
) -> None:
    """Ca phân biệt DUY NHẤT của lỗi múi giờ, và nó phải là 1 giờ sáng chứ không phải buổi tối.

    `reviewed_at` là TIMESTAMPTZ. 18:00 UTC ngày 11/8 chính là 01:00 sáng ngày 12/8 giờ Việt
    Nam (UTC+7). Viết `reviewed_at::date` trần thì Postgres quy về UTC và trả 11/8 — lượt ôn
    bị đẩy lùi một ngày, streak đứt sai, không có exception nào.

    Buổi tối KHÔNG phân biệt được: 20:00 giờ VN là 13:00 UTC, vẫn cùng ngày, nên code sai vẫn
    cho kết quả đúng.
    """
    card_id = _seed_card(db, owner.id, "mitigate")
    _seed_review(db, card_id, "GOOD", "2026-08-11 18:00:00+00")
    db.commit()

    # Ghim timezone phiên về UTC — KHÁC settings.tz — trước khi truy vấn.
    #
    # Không có dòng này thì ca test vô dụng: pgserver dựng Postgres kế thừa timezone của OS
    # máy chạy test, mà máy dev của dự án để giờ Việt Nam, tức trùng luôn settings.tz. Cast
    # trần khi đó cho CÙNG kết quả với cast tường minh, nên đổi `_local_date()` thành
    # cast trần vẫn thấy 5/5 xanh.
    #
    # SET LOCAL chứ không SET: nó chỉ sống trong transaction hiện tại và tự hết hiệu lực khi
    # commit/rollback. `SET` trần bám vào connection, mà connection được pool tái dùng, nên
    # nó sẽ rò sang test khác chạy sau.
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))

    assert repo.count_reviews_by_day(db, owner.id) == [(date(2026, 8, 12), 1, 0)]


def test_group_by_day_returns_ascending_and_counts_correctly(
    db: Session, owner: UserFixture
) -> None:
    card_id = _seed_card(db, owner.id, "mitigate")
    _seed_review(db, card_id, "GOOD", "2026-08-10 05:00:00+00")
    _seed_review(db, card_id, "HARD", "2026-08-10 06:00:00+00")
    _seed_review(db, card_id, "EASY", "2026-08-08 05:00:00+00")
    db.commit()

    assert repo.count_reviews_by_day(db, owner.id) == [
        (date(2026, 8, 8), 1, 0),
        (date(2026, 8, 10), 2, 0),
    ]


def test_group_by_day_separates_scheduled_and_practice(db: Session, owner: UserFixture) -> None:
    card_id = _seed_card(db, owner.id, "mitigate")
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode, "
            "reviewed_at) VALUES (:c,'GOOD',1,6,'SCHEDULED','2026-08-10 05:00:00+00')"
        ),
        {"c": card_id},
    )
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode, "
            "reviewed_at) VALUES (:c,'GOOD',6,6,'PRACTICE','2026-08-10 06:00:00+00')"
        ),
        {"c": card_id},
    )
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode, "
            "reviewed_at) VALUES (:c,'GOOD',6,6,'PRACTICE','2026-08-08 05:00:00+00')"
        ),
        {"c": card_id},
    )
    db.commit()

    # Ngày 08/8 CHỈ có lượt luyện — nó VẪN xuất hiện với scheduled = 0. Đó là hành vi đúng
    # của repository; việc loại nó khỏi streak là trách nhiệm của service.
    assert repo.count_reviews_by_day(db, owner.id) == [
        (date(2026, 8, 8), 0, 1),
        (date(2026, 8, 10), 1, 1),
    ]


def test_group_by_rating(db: Session, owner: UserFixture) -> None:
    card_id = _seed_card(db, owner.id, "mitigate")
    for rating in ("AGAIN", "GOOD", "GOOD", "EASY"):
        _seed_review(db, card_id, rating, "2026-08-10 05:00:00+00")
    db.commit()

    assert repo.count_reviews_by_rating(db, owner.id) == {"AGAIN": 1, "GOOD": 2, "EASY": 1}


def test_quiz_stats_by_type(db: Session, owner: UserFixture) -> None:
    """`avg_score` trả về nguyên trạng cho MỌI loại; việc bỏ nó đi với hai loại không có khái
    niệm điểm là quyết định của service, không phải của repository."""
    card_id = _seed_card(db, owner.id, "mitigate")
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
    for correct, score in ((True, 90), (False, 40)):
        db.execute(
            text(
                "INSERT INTO quiz_attempt (quiz_item_id, user_answer, correct, score) "
                "VALUES (:i, 'câu trả lời', :c, :s)"
            ),
            {"i": item_id, "c": correct, "s": score},
        )
    db.commit()

    assert repo.quiz_stats_by_type(db, owner.id) == {"FREE_WRITE": (2, 1, 65.0)}


def test_all_three_queries_return_empty_for_user_with_no_activity(
    db: Session, owner: UserFixture
) -> None:
    assert repo.count_reviews_by_day(db, owner.id) == []
    assert repo.count_reviews_by_rating(db, owner.id) == {}
    assert repo.quiz_stats_by_type(db, owner.id) == {}


def test_filter_by_user_id_does_not_leak_other_users_data(
    db: Session, owner: UserFixture
) -> None:
    """Không bảng nào trong ba câu (`review_log`, `srs_card`, `quiz_item`, `quiz_attempt`) có
    cột `user_id` — chủ sở hữu chỉ nằm ở `vocab_entry.user_id` (ràng buộc #13 CLAUDE.md).
    Xoá mệnh đề `WHERE user_id` khỏi bất kỳ hàm nào trong ba hàm cũng phải làm ca này đỏ.

    Dữ liệu của owner và của người khác CỐ Ý trùng ngày, trùng rating, trùng loại quiz — để
    nếu thiếu `WHERE user_id`, hai người bị GOM CHUNG vào đúng một ô (đếm tăng lên, điểm
    trung bình đổi) thay vì chỉ đơn giản thêm một dòng lạ dễ nhận ra.
    """
    other = create_user(db, SECOND_EMAIL)

    card_owner = _seed_card(db, owner.id, "mitigate")
    _seed_review(db, card_owner, "GOOD", "2026-08-10 05:00:00+00")
    vocab_owner = int(
        db.execute(
            text("SELECT vocab_entry_id FROM srs_card WHERE id = :c"), {"c": card_owner}
        ).scalar_one()
    )
    item_owner = int(
        db.execute(
            text(
                "INSERT INTO quiz_item (vocab_entry_id, type, payload, prompt_version) "
                "VALUES (:v, 'FREE_WRITE', '{}'::jsonb, 1) RETURNING id"
            ),
            {"v": vocab_owner},
        ).scalar_one()
    )
    db.execute(
        text(
            "INSERT INTO quiz_attempt (quiz_item_id, user_answer, correct, score) "
            "VALUES (:i, 'câu trả lời của owner', true, 90)"
        ),
        {"i": item_owner},
    )

    card_other = _seed_card(db, other.id, "mitigate")
    _seed_review(db, card_other, "GOOD", "2026-08-10 06:00:00+00")
    vocab_other = int(
        db.execute(
            text("SELECT vocab_entry_id FROM srs_card WHERE id = :c"), {"c": card_other}
        ).scalar_one()
    )
    item_other = int(
        db.execute(
            text(
                "INSERT INTO quiz_item (vocab_entry_id, type, payload, prompt_version) "
                "VALUES (:v, 'FREE_WRITE', '{}'::jsonb, 1) RETURNING id"
            ),
            {"v": vocab_other},
        ).scalar_one()
    )
    db.execute(
        text(
            "INSERT INTO quiz_attempt (quiz_item_id, user_answer, correct, score) "
            "VALUES (:i, 'câu trả lời của người khác', true, 50)"
        ),
        {"i": item_other},
    )
    db.commit()

    assert repo.count_reviews_by_day(db, owner.id) == [(date(2026, 8, 10), 1, 0)]
    assert repo.count_reviews_by_rating(db, owner.id) == {"GOOD": 1}
    assert repo.quiz_stats_by_type(db, owner.id) == {"FREE_WRITE": (1, 1, 90.0)}
