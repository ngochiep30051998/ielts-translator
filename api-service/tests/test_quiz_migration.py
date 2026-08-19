"""Bản port của `QuizMigrationIT`.

Canh hai thứ mà không test nào khác canh: **schema V5 khớp entity SQLAlchemy** (payload
JSONB ghi xuống rồi đọc lại vẫn nguyên hình), và **`find_reusable` lọc đúng bốn điều kiện**.

`find_reusable` là trái tim của cơ chế tiết kiệm quota: hỏng nó không làm gì đỏ, chỉ làm mỗi
lần mở màn quiz đốt thêm một lượt Gemini (bỏ lọt item cũ) hoặc trả lại câu vừa làm xong (bỏ
lọt điều kiện "chưa có lượt làm").

Đọc lại bằng SQL trần ở những chỗ cần chứng minh dữ liệu THẬT SỰ nằm dưới DB — identity map
của SQLAlchemy trả lại đúng object vừa tạo và làm phép so xanh giả.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import models as _auth_models  # noqa: F401  (đăng ký bảng app_user vào metadata)
from app.quiz import repository
from app.quiz.models import QuizAttempt, QuizItem, QuizType
from app.vocabulary.models import VocabEntry
from tests.conftest import UserFixture


def _saved_word(db: Session, user_id: int) -> VocabEntry:
    """user_id là NOT NULL từ V6 — dựng entry mà quên chủ sở hữu là nổ ngay lúc insert."""
    entry = VocabEntry(
        user_id=user_id,
        term="mitigate",
        lemma="mitigate",
        lang="en",
        pos="verb",
        meaning_vi="giảm nhẹ",
        collocations=[],
        examples=[],
    )
    db.add(entry)
    db.flush()
    return entry


def _saved_item(db: Session, entry: VocabEntry) -> QuizItem:
    item = QuizItem(
        vocab_entry_id=entry.id,
        type=QuizType.FILL_BLANK.value,
        payload={"sentence": "We must ___ the risk.", "answer": "mitigate"},
        prompt_version=1,
    )
    db.add(item)
    db.flush()
    return item


def _count(db: Session, model: Any) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


def test_v5_builds_tables_and_jsonb_payload_reads_back_intact(
    db: Session, owner: UserFixture
) -> None:
    """V5 dựng được bảng và entity khớp schema — payload JSONB đọc lại nguyên vẹn.

    Đây là chốt "migration và entity không lệch nhau". Bên Java `ddl-auto: validate` bắt được
    lệch cột lúc khởi động; SQLAlchemy không có cơ chế đó, nên phép ghi/đọc thật ở đây là thứ
    duy nhất đứng thay.
    """
    item = _saved_item(db, _saved_word(db, owner.id))

    db.add(
        QuizAttempt(
            quiz_item_id=item.id,
            user_answer="mitigate",
            correct=True,
            score=100,
            ai_feedback=None,
            improved_version=None,
        )
    )
    db.commit()

    # expire_all buộc SELECT lại từ DB thay vì trả object đang nằm trong identity map — không
    # có dòng này thì phép so dưới đây chỉ chứng minh Python nhớ được thứ Python vừa tạo.
    db.expire_all()
    reloaded_item = db.get(QuizItem, item.id)
    assert reloaded_item is not None
    assert reloaded_item.payload["answer"] == "mitigate"
    assert reloaded_item.payload["sentence"] == "We must ___ the risk."
    assert reloaded_item.type == QuizType.FILL_BLANK.value
    assert _count(db, QuizAttempt) == 1


def test_improved_version_column_saves_and_reads_back(db: Session, owner: UserFixture) -> None:
    """Chỗ DUY NHẤT giữ câu Gemini viết lại.

    Cột này tách khỏi `ai_feedback` vì hợp đồng API trả hai trường khác nhau; nhét chung một
    cột rồi tách bằng chuỗi phân cách sẽ hỏng ở lần đầu Gemini trả đúng dấu phân cách đó.
    """
    item = _saved_item(db, _saved_word(db, owner.id))

    attempt = QuizAttempt(
        quiz_item_id=item.id,
        user_answer="We must mitigate it.",
        correct=True,
        score=90,
        ai_feedback="Câu ổn.",
        improved_version="We must mitigate the risk effectively.",
    )
    db.add(attempt)
    db.commit()

    stored_in_db = db.execute(
        text("SELECT improved_version FROM quiz_attempt WHERE id = :i"), {"i": attempt.id}
    ).scalar_one()
    assert stored_in_db == "We must mitigate the risk effectively."


def test_deleting_word_from_notebook_cascade_clears_quiz_item_and_quiz_attempt(
    db: Session, owner: UserFixture
) -> None:
    """Xoá một từ phải cuốn theo cả đề lẫn lịch sử làm bài của từ đó.

    Không có cascade thì `quiz_item` mồ côi vẫn nằm lại, và khoá ngoại sẽ chặn lệnh xoá —
    người dùng bấm xoá từ và nhận về 500.
    """
    entry = _saved_word(db, owner.id)
    item = _saved_item(db, entry)
    db.add(
        QuizAttempt(quiz_item_id=item.id, user_answer="x", correct=False, score=0)
    )
    db.commit()

    db.execute(text("DELETE FROM vocab_entry WHERE id = :v"), {"v": entry.id})
    db.commit()

    assert _count(db, QuizItem) == 0
    assert _count(db, QuizAttempt) == 0


def test_find_reusable_skips_attempted_item_and_wrong_prompt_version_item(
    db: Session, owner: UserFixture
) -> None:
    """Ba item cùng từ, cùng loại: một dùng được, một đã có lượt làm, một sai prompt_version.
    Chỉ item đầu được trả về.

    Ba điều kiện hỏng theo ba kiểu riêng và đều IM LẶNG: bỏ "chưa có lượt làm" là câu vừa làm
    xong hiện lại ở đề sau; bỏ `prompt_version` là sửa prompt xong đề cũ vẫn sống mãi.
    """
    entry = _saved_word(db, owner.id)

    usable_item = _saved_item(db, entry)

    attempted_item = _saved_item(db, entry)
    db.add(
        QuizAttempt(quiz_item_id=attempted_item.id, user_answer="x", correct=False, score=0)
    )

    wrong_version_item = _saved_item(db, entry)
    wrong_version_item.prompt_version = 99
    db.flush()
    db.commit()

    still_reusable = repository.find_reusable(
        db, owner.id, [entry.id], [QuizType.FILL_BLANK], 1
    )

    assert [item.id for item in still_reusable] == [usable_item.id]


def test_find_reusable_does_not_return_another_users_quiz_items(
    db: Session, owner: UserFixture, user_b: UserFixture
) -> None:
    """Điều kiện thứ tư — chủ sở hữu.

    Bản Java không có test riêng cho nhánh này vì `MultiUserIsolationIT` phủ nó ở tầng HTTP.
    Đưa xuống đây vì `find_reusable` nhận `vocab_ids` do người gọi truyền vào: một người gọi
    tương lai quên lọc từ trước khi gọi sẽ không có lưới nào đỡ nếu chính câu truy vấn cũng
    không lọc (ràng buộc #13).
    """
    b_word = _saved_word(db, user_b.id)
    b_item = _saved_item(db, b_word)
    db.commit()

    # A hỏi thẳng bằng id từ của B — đúng hình dạng của lỗ IDOR.
    assert repository.find_reusable(db, owner.id, [b_word.id], [QuizType.FILL_BLANK], 1) == []
    # Còn chính B thì vẫn thấy đề của mình: khẳng định trên không xanh vì câu truy vấn chết.
    assert [item.id for item in repository.find_reusable(
        db, user_b.id, [b_word.id], [QuizType.FILL_BLANK], 1
    )] == [b_item.id]
