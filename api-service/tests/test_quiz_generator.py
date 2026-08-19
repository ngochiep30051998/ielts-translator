"""Bản port của `QuizGeneratorIT`.

Trọng tâm là hai bất biến tiết kiệm quota, cả hai đều hỏng im lặng:

* **một lô = một call** — 10 từ FILL_BLANK tốn đúng một lượt gọi Gemini, không phải mười;
* **tái dùng trước, sinh sau** — `find_reusable` + `prompt_version` là cặp quyết định đề cũ
  còn sống hay đã hết hiệu lực.

Ở đây `GeminiGia` mạnh hơn `@MockitoBean` một bậc: gọi Gemini nhiều hơn số phản hồi đã xếp
sẵn thì ném AssertionError ngay tại điểm gọi, nên "cache không ăn" không thể trốn qua được
một khẳng định `times(1)` bị quên.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import models as _auth_models  # noqa: F401  (đăng ký bảng app_user vào metadata)
from app.common.errors import AppError, ErrorCode
from app.quiz import generator
from app.quiz.models import QuizAttempt, QuizItem, QuizType
from app.vocabulary.models import VocabEntry
from tests.conftest import FakeGemini, UserFixture


def _save_words(db: Session, user_id: int, n: int) -> list[int]:
    """n từ w0..w(n-1), mỗi từ mang sẵn nghĩa tiếng Việt để FREE_WRITE có gì mà dựng đề."""
    ids: list[int] = []
    for i in range(n):
        entry = VocabEntry(
            user_id=user_id,
            term=f"w{i}",
            lemma=f"w{i}",
            lang="en",
            pos="verb",
            meaning_vi=f"nghĩa của w{i}",
            collocations=[],
            examples=[],
        )
        db.add(entry)
        db.flush()
        ids.append(entry.id)
    return ids


def _fill_blank_batch(n: int) -> dict[str, Any]:
    """Lô fill-blank HỢP LỆ cho n từ: câu có `___`, đáp án không lộ trong câu lẫn trong gợi ý."""
    return {
        "items": [
            {
                "term": f"w{i}",
                "sentence": "They must ___ the risk.",
                "answer": f"w{i}",
                "hint": f"gợi ý {i}",
            }
            for i in range(n)
        ]
    }


def _count(db: Session, model: Any) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


def _ids(built: list[tuple[QuizItem, VocabEntry]]) -> list[int]:
    return [item.id for item, _ in built]


def test_one_batch_of_six_words_costs_exactly_one_gemini_call(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Sáu từ FILL_BLANK tốn ĐÚNG MỘT call, không phải sáu.

    Đây là lý do tồn tại của `build_items` theo lô. Sinh từng từ một vẫn ra kết quả đúng, chỉ
    đắt gấp sáu lần và chậm gấp sáu lần — không có gì đỏ, hoá đơn Gemini mới là chỗ báo.
    """
    ids = _save_words(db, owner.id, 6)
    gemini.queue_json(_fill_blank_batch(6))

    built = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)

    assert len(built) == 6
    assert gemini.call_count == 1


def test_free_write_costs_no_gemini_call_when_generating_quiz(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Đề FREE_WRITE dựng thẳng từ sổ từ — không có gì để hỏi Gemini lúc sinh đề.

    Câu hỏi phải mang cả `term` lẫn nghĩa tiếng Việt: thiếu nghĩa thì người học không biết
    đang được yêu cầu dùng từ theo nghĩa nào.
    """
    ids = _save_words(db, owner.id, 3)

    built = generator.build_items(db, owner.id, ids, QuizType.FREE_WRITE)

    assert len(built) == 3
    question = built[0][0].payload["question"]
    assert "w0" in question
    assert "nghĩa của w0" in question
    assert gemini.requests == []


def test_second_generation_reuses_items_not_yet_attempted(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Sinh đề hai lần liên tiếp: lần hai trả về CÙNG id item và không gọi Gemini thêm.

    Chỉ xếp sẵn MỘT phản hồi: lượt gọi thứ hai (nếu có) sẽ nổ AssertionError trong
    `GeminiGia` kèm URL, nên test này không thể xanh giả.
    """
    ids = _save_words(db, owner.id, 3)
    gemini.queue_json(_fill_blank_batch(3))

    first_run_ids = _ids(generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK))
    second_run_ids = _ids(generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK))

    assert second_run_ids == first_run_ids
    assert gemini.call_count == 1
    # Và không đẻ thêm bản ghi nào: tái dùng nghĩa là dùng lại, không phải sinh bản sao.
    assert _count(db, QuizItem) == 3


def test_item_that_already_has_attempt_is_not_reused(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Câu đã làm rồi phải được thay bằng câu mới.

    Bỏ điều kiện này là người học mở lại màn quiz và gặp đúng câu vừa trả lời xong — ôn tập
    biến thành đọc lại đáp án vừa nhớ.
    """
    ids = _save_words(db, owner.id, 1)
    gemini.queue_json(_fill_blank_batch(1), times=2)

    first_item = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]
    db.add(
        QuizAttempt(
            quiz_item_id=first_item.id, user_answer="w0", correct=True, score=100
        )
    )
    db.flush()

    second_item = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]

    assert second_item.id != first_item.id
    assert gemini.call_count == 2


def test_item_with_old_prompt_version_is_discarded_and_regenerated(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Đổi `prompt_version` của item cũ thì lần sinh sau phải gọi Gemini lại.

    Đây là NỬA CÒN LẠI của cơ chế tái dùng: sửa nội dung một file prompt rồi tăng `version:`
    ở đầu file là cách DUY NHẤT làm đề cũ hết hiệu lực (ràng buộc #5). Quên tăng version thì
    người dùng nhận đề sinh bằng prompt cũ mãi mãi và không có gì đỏ — nên item mới phải mang
    đúng version đang hiệu lực, không chỉ "khác id".
    """
    ids = _save_words(db, owner.id, 1)
    gemini.queue_json(_fill_blank_batch(1), times=2)

    first_item = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]
    db.execute(
        text("UPDATE quiz_item SET prompt_version = 99 WHERE id = :i"), {"i": first_item.id}
    )

    second_item = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]

    assert second_item.id != first_item.id
    assert second_item.prompt_version == generator.prompt_version_for(QuizType.FILL_BLANK)
    assert gemini.call_count == 2


def test_batch_with_broken_item_drops_only_that_item(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Câu giữa thiếu `___` → bỏ đúng câu đó, hai câu còn lại vẫn dùng được.

    Khác bộ kiểm mồi nhử của srs một cách CÓ CHỦ Ý (bên đó loại cả lô): người dùng đang đứng
    chờ, bắt họ đợi thêm một lượt Gemini chỉ vì một câu hỏng là đắt vô lý.
    """
    ids = _save_words(db, owner.id, 3)
    gemini.queue_json(
        {
            "items": [
                {"term": "w0", "sentence": "We must ___ it.", "answer": "w0", "hint": "x"},
                {"term": "w1", "sentence": "No blank here.", "answer": "w1", "hint": "x"},
                {"term": "w2", "sentence": "They ___ risk.", "answer": "w2", "hint": "x"},
            ]
        }
    )

    built = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)

    assert len(built) == 2
    # Câu hỏng KHÔNG được lưu xuống DB: lưu rồi thì nó lọt `find_reusable` ở lượt sau.
    assert _count(db, QuizItem) == 2


def test_entire_batch_broken_raises_parse_error(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Không dựng nổi câu nào thì ném PARSE_ERROR, KHÔNG trả mảng rỗng.

    Mảng rỗng ở đây là nói dối: nó trùng hình dạng với "sổ chưa có từ nào đủ điều kiện" — một
    trạng thái bình thường — nên UI sẽ báo "chưa có gì để ôn" trong khi Gemini đang trả rác.
    """
    ids = _save_words(db, owner.id, 2)
    gemini.queue_json(
        {
            "items": [
                {"term": "w0", "sentence": "No blank.", "answer": "w0", "hint": "x"},
                {"term": "w1", "sentence": "Also no blank.", "answer": "w1", "hint": "x"},
            ]
        }
    )

    with pytest.raises(AppError) as err:
        generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)
    assert err.value.code is ErrorCode.PARSE_ERROR


def test_fill_blank_payload_keeps_answer_and_hint(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Đáp án nằm trong `payload`, không nằm trong DTO — đó là chỗ duy nhất giữ nó để chấm
    bài sau này."""
    ids = _save_words(db, owner.id, 1)
    gemini.queue_json(_fill_blank_batch(1))

    item = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]

    assert item.payload["answer"] == "w0"
    assert "sentence" in item.payload
    assert "hint" in item.payload


def test_options_shuffled_but_correct_index_still_points_to_answer(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Xáo xong thì `correct_index` phải đi theo đáp án, không đứng yên.

    Xáo mà quên dời index là chấm sai TOÀN BỘ câu trắc nghiệm mà không lỗi nào nổ ra: người
    học chọn đúng vẫn bị báo sai.
    """
    ids = _save_words(db, owner.id, 1)
    gemini.queue_json(
        {
            "items": [
                {
                    "term": "w0",
                    "question": "Cụm nào tự nhiên?",
                    "options": ["đúng", "sai 1", "sai 2", "sai 3"],
                    "correct_index": 0,
                }
            ]
        }
    )

    item = generator.build_items(db, owner.id, ids, QuizType.COLLOCATION_CHOICE)[0][0]

    options = item.payload["options"]
    correct_index = item.payload["correct_index"]
    assert sorted(options) == sorted(["đúng", "sai 1", "sai 2", "sai 3"])
    assert options[correct_index] == "đúng"


def test_shuffle_actually_happens(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """40 lần sinh không thể lần nào đáp án cũng rơi vào vị trí 0.

    Gemini có xu hướng đặt đáp án đúng ở vị trí đầu; không xáo thì quiz đoán được mà không
    cần biết từ. Xác suất dương tính giả (xáo thật mà 40 lần đều ra cùng một vị trí) là
    (1/4)^39 — coi như không xảy ra.
    """
    ids = _save_words(db, owner.id, 1)
    gemini.queue_json(
        {
            "items": [
                {
                    "term": "w0",
                    "question": "Cụm nào tự nhiên?",
                    "options": ["đúng", "sai 1", "sai 2", "sai 3"],
                    "correct_index": 0,
                }
            ]
        },
        times=40,
    )

    positions: list[int] = []
    for _ in range(40):
        # Xoá item cũ để lượt sau không rơi vào đường tái dùng.
        db.execute(text("DELETE FROM quiz_item"))
        item = generator.build_items(db, owner.id, ids, QuizType.COLLOCATION_CHOICE)[0][0]
        positions.append(item.payload["correct_index"])

    assert len(set(positions)) > 1, (
        "40 lần sinh mà đáp án luôn ở cùng một vị trí nghĩa là không hề xáo"
    )
