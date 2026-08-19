"""Bản port của `QuizSrsIsolationIT`.

Bất biến quan trọng nhất của Phase 3: **làm quiz KHÔNG được đụng vào lịch ôn SRS.**

Chụp ảnh trước/sau bằng SQL trần chứ không qua ORM — bộ nhớ phiên của ORM có thể trả lại
đúng object cũ và làm phép so xanh giả.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.quiz import service as quiz_service
from app.quiz.models import GenerateQuizRequest, QuizType
from tests.conftest import FakeGemini, UserFixture


def _seed(db: Session, user_id: int, term: str, repetitions: int, lapses: int) -> int:
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
    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses, "
            "                      ease_factor, interval_days) "
            "VALUES (:v, CURRENT_DATE + 3, 'REVIEW', :r, :l, 2.36, 7)"
        ),
        {"v": vocab_id, "r": repetitions, "l": lapses},
    )
    db.commit()
    return vocab_id


def _snapshot_srs(db: Session) -> list[tuple[Any, ...]]:
    db.expire_all()
    return [
        tuple(row)
        for row in db.execute(
            text(
                "SELECT id, vocab_entry_id, ease_factor, interval_days, repetitions, lapses, "
                "       due_date, state FROM srs_card ORDER BY id"
            )
        )
    ]


def _snapshot_review_log(db: Session) -> list[tuple[Any, ...]]:
    db.expire_all()
    return [
        tuple(row)
        for row in db.execute(
            text(
                "SELECT id, card_id, rating, prev_interval, new_interval "
                "FROM review_log ORDER BY id"
            )
        )
    ]


def _seed_review_log(db: Session, vocab_entry_id: int) -> None:
    """Gieo sẵn lịch sử ôn để phép so cuối bài có gì để so.

    Không có bước này thì `review_log` rỗng suốt bài và khẳng định "không đổi dòng nào" rút
    về `[] == []` — nó bắt được ca INSERT nhưng bỏ lọt hoàn toàn ca một hồi quy tương lai
    SỬA hoặc XOÁ dòng có sẵn (ví dụ ai đó thêm "làm quiz đúng thì hạ lapses của lượt ôn gần
    nhất").
    """
    card_id = db.execute(
        text("SELECT id FROM srs_card WHERE vocab_entry_id = :v"), {"v": vocab_entry_id}
    ).scalar_one()
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval) "
            "VALUES (:c, 'GOOD', 0, 1), (:c, 'HARD', 1, 2)"
        ),
        {"c": card_id},
    )
    db.commit()


_FILL_BLANK = {
    "items": [
        {
            "term": "mitigate",
            "sentence": "They must ___ it.",
            "answer": "mitigate",
            "hint": "gợi ý",
        },
        {
            "term": "resilient",
            "sentence": "She is ___ enough.",
            "answer": "resilient",
            "hint": "gợi ý",
        },
    ]
}

_COLLOCATION = {
    "items": [
        {
            "term": "mitigate",
            "question": "Cụm nào tự nhiên?",
            "options": ["mitigate risk", "mitigate cake", "mitigate blue", "mitigate loud"],
            "correct_index": 0,
        },
        {
            "term": "resilient",
            "question": "Cụm nào tự nhiên?",
            "options": [
                "resilient economy",
                "resilient cake",
                "resilient blue",
                "resilient loud",
            ],
            "correct_index": 0,
        },
    ]
}

_GRADE_FREE_WRITE = {
    "meaning_ok": True,
    "grammar_ok": False,
    "band_ok": False,
    "score": 55,
    "feedback_vi": "Ngữ pháp còn lỗi.",
    "improved_version": "Better.",
}


def _complete_one_quiz_set(
    db: Session, gemini: FakeGemini, user_id: int, quiz_type: QuizType
) -> int:
    """Sinh đề một loại rồi nộp hết, cả câu đúng lẫn câu sai. Trả về số câu đã nộp."""
    if quiz_type is QuizType.FILL_BLANK:
        gemini.queue_json(_FILL_BLANK)
    elif quiz_type is QuizType.COLLOCATION_CHOICE:
        gemini.queue_json(_COLLOCATION)

    quiz_items = quiz_service.generate(
        db, user_id, GenerateQuizRequest(count=10, type=quiz_type)
    )
    assert quiz_items, f"{quiz_type} phải sinh được đề"

    if quiz_type is QuizType.FREE_WRITE:
        # Mỗi câu FREE_WRITE là một lượt chấm riêng bằng Gemini.
        gemini.queue_json(_GRADE_FREE_WRITE, times=len(quiz_items))

    for i, item in enumerate(quiz_items):
        # Xen kẽ đúng/sai để chắc chắn cả hai nhánh chấm đều chạy.
        quiz_service.answer(
            db, user_id, item.id, "0" if i % 2 == 0 else "câu trả lời bất kỳ"
        )
    return len(quiz_items)


def test_taking_quiz_never_touches_srs(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Làm hết một đề cả ba loại xong, `srs_card` và `review_log` không đổi một dòng nào."""
    first_vocab_id = _seed(db, owner.id, "mitigate", 3, 1)
    _seed(db, owner.id, "resilient", 5, 0)
    _seed_review_log(db, first_vocab_id)

    srs_before = _snapshot_srs(db)
    review_log_before = _snapshot_review_log(db)
    assert len(srs_before) == 2
    # Chốt chống phép so rỗng: có dòng thật thì so snapshot mới có nghĩa.
    assert len(review_log_before) == 2

    submitted_count = 0
    submitted_count += _complete_one_quiz_set(db, gemini, owner.id, QuizType.FILL_BLANK)
    submitted_count += _complete_one_quiz_set(db, gemini, owner.id, QuizType.COLLOCATION_CHOICE)
    submitted_count += _complete_one_quiz_set(db, gemini, owner.id, QuizType.FREE_WRITE)

    # Không có điểm này thì test xanh cả khi code chết: "không đổi gì" là hiển nhiên khi
    # chẳng có gì chạy.
    assert submitted_count > 0
    attempt_count = db.execute(text("SELECT count(*) FROM quiz_attempt")).scalar_one()
    assert attempt_count == submitted_count

    assert _snapshot_srs(db) == srs_before
    # So snapshot từng cột, không so count(*): count bắt được INSERT/DELETE nhưng không bắt
    # được UPDATE một dòng có sẵn.
    assert _snapshot_review_log(db) == review_log_before


def test_quiz_module_reads_srs_through_exactly_one_gateway(db: Session) -> None:
    """ACL: `app.quiz` không được import gì từ `app.srs` ngoài `candidates.py`, và file đó
    chỉ được đọc.

    Bên Java, bất biến này chỉ tồn tại trong lời hứa của người viết. Ở đây nó là một phép
    thử chạy được — cùng tinh thần với chính `QuizSrsIsolationIT`.
    """
    import ast
    from pathlib import Path

    quiz_dir = Path(__file__).resolve().parent.parent / "app" / "quiz"
    violations: list[str] = []
    for path in sorted(quiz_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module_names: list[str] = []
            if isinstance(node, ast.Import):
                module_names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                module_names = [node.module]
            for t in module_names:
                if t.startswith("app.srs") and path.name != "candidates.py":
                    violations.append(f"{path.name} import {t}")

    assert violations == [], (
        "quiz đọc dữ liệu SRS qua ĐÚNG một chỗ là candidates.py và không bao giờ ghi. "
        f"Vi phạm: {violations}"
    )

    source = (quiz_dir / "candidates.py").read_text(encoding="utf-8").upper()
    for forbidden_word in ("INSERT ", "UPDATE ", "DELETE "):
        assert forbidden_word not in source, (
            f"candidates.py chỉ được SELECT, thấy {forbidden_word.strip()}"
        )
