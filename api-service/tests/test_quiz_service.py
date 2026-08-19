"""Bản port của `QuizServiceIT`.

Ba nhóm khẳng định, đúng theo bản Java:

1. **chọn ứng viên** — ai được đưa vào đề và theo thứ tự nào;
2. **đếm call Gemini** — tái dùng có ăn không, `prompt_version` có làm cũ đi không, FREE_WRITE
   có thật sự miễn phí lúc sinh đề không;
3. **chấm bài** — ranh giới giữa "trả lời sai" (200) và "lỗi" (4xx/5xx).

Chỗ khác bản Java: Mockito đếm được `eq(GeminiTimeout.QUIZ_GENERATE)` vì nó chặn ở chữ ký
hàm, còn `GeminiGia` chặn ở tầng HTTP nên không thấy mức timeout. Fixture `timeout_tiers` dưới
đây bù lại đúng phần đó — mức timeout sai không làm gì đỏ, chỉ làm một lượt sinh đề đứt giữa
chừng trên máy người dùng khi Gemini chậm thật.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import models as _auth_models  # noqa: F401  (đăng ký bảng app_user vào metadata)
from app.common.errors import AppError, ErrorCode
from app.common.gemini import GeminiTimeout
from app.quiz import service
from app.quiz.models import GenerateQuizRequest, QuizAttempt, QuizItem, QuizType
from app.vocabulary.models import VocabEntry
from tests.conftest import FakeGemini, UserFixture


@pytest.fixture
def timeout_tiers(
    monkeypatch: pytest.MonkeyPatch, gemini: FakeGemini
) -> Iterator[list[GeminiTimeout]]:
    """Ghi lại MỨC TIMEOUT của từng lượt gọi Gemini, theo đúng thứ tự gọi.

    Bọc `generate_json` chứ không thay thế nó: toàn bộ đường đi thật (dựng body, đọc
    candidate, map status code) vẫn chạy qua `GeminiGia` như mọi test khác.
    """
    from app.common.gemini import GeminiClient

    recorded_tiers: list[GeminiTimeout] = []
    original_generate_json = GeminiClient.generate_json

    def _record(
        self: GeminiClient, prompt: str, response_schema: dict[str, Any], tier: GeminiTimeout
    ) -> Any:
        recorded_tiers.append(tier)
        return original_generate_json(self, prompt, response_schema, tier)

    monkeypatch.setattr(GeminiClient, "generate_json", _record)
    yield recorded_tiers


def _save_word(db: Session, user_id: int, term: str) -> int:
    entry = VocabEntry(
        user_id=user_id,
        term=term,
        lemma=term,
        lang="en",
        pos="verb",
        meaning_vi=f"nghĩa của {term}",
        collocations=[],
        examples=[],
    )
    db.add(entry)
    db.flush()
    return entry.id


def _srs_card(db: Session, vocab_id: int, repetitions: int, lapses: int) -> None:
    """Thẻ SRS của một từ. `repetitions >= 1` là điều kiện lọt vào danh sách ứng viên."""
    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses) "
            "VALUES (:v, CURRENT_DATE, 'REVIEW', :r, :l)"
        ),
        {"v": vocab_id, "r": repetitions, "l": lapses},
    )
    db.flush()


def _batch_fill_blank(*terms: str) -> dict[str, Any]:
    return {
        "items": [
            {
                "term": term,
                "sentence": "They must ___ the risk.",
                "answer": term,
                "hint": "gợi ý",
            }
            for term in terms
        ]
    }


def _grade_free_write(
    meaning_ok: bool, grammar_ok: bool, band_ok: bool, score: int
) -> dict[str, Any]:
    return {
        "meaning_ok": meaning_ok,
        "grammar_ok": grammar_ok,
        "band_ok": band_ok,
        "score": score,
        "feedback_vi": "Nhận xét tiếng Việt.",
        "improved_version": "A better sentence.",
    }


def _request_by_count(count: int, quiz_type: QuizType) -> GenerateQuizRequest:
    return GenerateQuizRequest(count=count, type=quiz_type)


def _count(db: Session, model: Any) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


# ── chọn ứng viên ─────────────────────────────────────────────────────────────


def test_word_never_reviewed_is_not_put_into_the_quiz(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """`repetitions = 0` nghĩa là người học chưa từng gặp lại từ đó — hỏi là phạt oan.

    Gemini vẫn được xếp sẵn câu cho CẢ HAI từ: nếu câu lọc hỏng thì từ "fresh" sẽ lọt vào đề
    một cách hoàn toàn im lặng, và khẳng định dưới đây là chỗ duy nhất bắt được.
    """
    reviewed_id = _save_word(db, owner.id, "reviewed")
    _srs_card(db, reviewed_id, 2, 0)
    unreviewed = _save_word(db, owner.id, "fresh")
    _srs_card(db, unreviewed, 0, 0)
    gemini.queue_json(_batch_fill_blank("reviewed", "fresh"))

    quiz_items = service.generate(db, owner.id, _request_by_count(10, QuizType.FILL_BLANK))

    assert [item.vocab_entry_id for item in quiz_items] == [reviewed_id]


def test_prioritizes_least_asked_words_then_most_forgotten_words(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Cùng số lượt bị hỏi thì từ hay quên (lapses cao) đứng trước.

    So THỨ TỰ chứ không so tập hợp: mất `ORDER BY c.lapses DESC` vẫn ra đúng hai từ đó, chỉ
    là người học được ôn thứ mình đã nhớ trước thứ mình hay quên.
    """
    rarely_forgotten = _save_word(db, owner.id, "low")
    _srs_card(db, rarely_forgotten, 3, 0)
    often_forgotten = _save_word(db, owner.id, "high")
    _srs_card(db, often_forgotten, 3, 9)
    gemini.queue_json(_batch_fill_blank("high", "low"))

    quiz_items = service.generate(db, owner.id, _request_by_count(10, QuizType.FILL_BLANK))

    assert [item.vocab_entry_id for item in quiz_items] == [often_forgotten, rarely_forgotten]


def test_notebook_with_only_unreviewed_words_returns_empty_and_calls_no_gemini(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """"Chưa ôn từ nào đủ điều kiện" là trạng thái BÌNH THƯỜNG, không phải lỗi.

    Ném ở đây sẽ buộc phải đẻ thêm một ErrorCode cho một tình huống hoàn toàn bình thường, và
    UI phải học cách phân biệt nó với lỗi thật.
    """
    _srs_card(db, _save_word(db, owner.id, "fresh"), 0, 0)

    assert service.generate(db, owner.id, _request_by_count(10, QuizType.FILL_BLANK)) == []
    assert gemini.requests == []


def test_empty_notebook_returns_empty_list_without_raising(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Người dùng mới tinh mở màn quiz — không được nhận lỗi."""
    assert service.generate(db, owner.id, _request_by_count(10, QuizType.FILL_BLANK)) == []
    assert gemini.requests == []


def test_explicit_vocab_ids_skip_the_repetitions_condition(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Người dùng tự chọn từ thì họ đã quyết định muốn ôn từ đó — điều kiện `repetitions >= 1`
    chỉ áp cho đường chọn TỰ ĐỘNG theo `count`."""
    unreviewed = _save_word(db, owner.id, "fresh")
    _srs_card(db, unreviewed, 0, 0)
    gemini.queue_json(_batch_fill_blank("fresh"))

    quiz_items = service.generate(
        db, owner.id, GenerateQuizRequest(vocab_ids=[unreviewed], type=QuizType.FILL_BLANK)
    )

    assert len(quiz_items) == 1


def test_vocab_ids_that_all_do_not_exist_return_empty_and_call_no_gemini(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Id lạ bị bỏ qua chứ không thành lỗi — và không được đốt một lượt Gemini nào cho một
    request chẳng có từ nào để hỏi."""
    quiz_items = service.generate(
        db, owner.id, GenerateQuizRequest(vocab_ids=[999_999], type=QuizType.FILL_BLANK)
    )

    assert quiz_items == []
    assert gemini.requests == []


def test_count_larger_than_the_candidate_pool_returns_exactly_the_candidate_count(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """[Q1] Xin 10 câu mà chỉ có 4 từ đủ điều kiện → đúng 4 câu, không đệm thêm.

    "Đệm thêm" ở đây nghĩa là hạ điều kiện ứng viên xuống cho đủ số — tức là hỏi từ người học
    chưa từng ôn, đúng thứ mà điều kiện `repetitions >= 1` sinh ra để tránh.
    """
    for i in range(4):
        _srs_card(db, _save_word(db, owner.id, f"w{i}"), 2, 0)
    gemini.queue_json(_batch_fill_blank("w0", "w1", "w2", "w3"))

    assert len(service.generate(db, owner.id, _request_by_count(10, QuizType.FILL_BLANK))) == 4


def test_each_word_in_the_batch_generates_exactly_one_question(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """3 từ ra 3 câu, không nhân bản."""
    for i in range(3):
        _srs_card(db, _save_word(db, owner.id, f"w{i}"), 2, 0)
    gemini.queue_json(_batch_fill_blank("w0", "w1", "w2"))

    assert len(service.generate(db, owner.id, _request_by_count(3, QuizType.FILL_BLANK))) == 3


# ── đếm call Gemini ───────────────────────────────────────────────────────────


def test_generating_twice_in_a_row_reuses_the_quiz_the_second_time(
    db: Session, gemini: FakeGemini, owner: UserFixture, timeout_tiers: list[GeminiTimeout]
) -> None:
    """[R4] Lần hai trả về đúng những id cũ và tốn 0 call Gemini thêm.

    Đây là đường người dùng đi nhiều nhất — đóng rồi mở lại màn quiz. Mất cơ chế tái dùng thì
    mỗi lần mở là một lượt Gemini, không có gì đỏ, chỉ có hạn mức bốc hơi.
    """
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    gemini.queue_json(_batch_fill_blank("w0"))

    first_run = service.generate(db, owner.id, _request_by_count(5, QuizType.FILL_BLANK))
    second_run = service.generate(db, owner.id, _request_by_count(5, QuizType.FILL_BLANK))

    assert [i.id for i in second_run] == [i.id for i in first_run]
    # Lọc theo mức QUIZ_GENERATE chứ không đếm tổng: mức khác là của luồng khác, đếm lẫn vào
    # đây là test đỏ ngẫu nhiên không tái hiện được.
    assert timeout_tiers.count(GeminiTimeout.QUIZ_GENERATE) == 1


def test_changing_prompt_version_in_db_makes_the_next_generation_call_gemini_again(
    db: Session, gemini: FakeGemini, owner: UserFixture, timeout_tiers: list[GeminiTimeout]
) -> None:
    """Đề sinh bằng prompt cũ phải hết hiệu lực.

    `prompt_version` nằm trong điều kiện của `find_reusable` — đó là cách DUY NHẤT làm đề cũ
    hết hiệu lực sau khi sửa nội dung prompt (ràng buộc #5).
    """
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    gemini.queue_json(_batch_fill_blank("w0"), times=2)

    service.generate(db, owner.id, _request_by_count(5, QuizType.FILL_BLANK))
    db.execute(text("UPDATE quiz_item SET prompt_version = 99"))
    service.generate(db, owner.id, _request_by_count(5, QuizType.FILL_BLANK))

    assert timeout_tiers.count(GeminiTimeout.QUIZ_GENERATE) == 2


def test_free_write_costs_no_gemini_call_when_generating_the_quiz(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """[Q1] FREE_WRITE dựng đề từ chính sổ từ."""
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)

    assert len(service.generate(db, owner.id, _request_by_count(5, QuizType.FREE_WRITE))) == 1
    assert gemini.requests == []


def test_whole_batch_broken_raises_parse_error(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Câu Gemini trả về không có chỗ trống → không dựng nổi item nào → PARSE_ERROR."""
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    gemini.queue_json(
        {
            "items": [
                {
                    "term": "w0",
                    "sentence": "Khong co cho trong.",
                    "answer": "w0",
                    "hint": "x",
                }
            ]
        }
    )

    with pytest.raises(AppError) as err:
        service.generate(db, owner.id, _request_by_count(5, QuizType.FILL_BLANK))
    assert err.value.code is ErrorCode.PARSE_ERROR


def test_generated_quiz_stays_in_the_db(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Không lưu thì không có gì để tái dùng ở lượt sau."""
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    gemini.queue_json(_batch_fill_blank("w0"))

    service.generate(db, owner.id, _request_by_count(5, QuizType.FILL_BLANK))

    assert _count(db, QuizItem) == 1


# ── chấm bài ──────────────────────────────────────────────────────────────────


def test_grading_the_same_item_twice_writes_two_history_rows(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """`quiz_attempt` là LỊCH SỬ, không phải trạng thái hiện tại.

    Ghi đè thay vì thêm dòng làm hỏng luôn tiêu chí xếp ưu tiên ứng viên — nó đếm số lượt làm
    của từng từ.
    """
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    gemini.queue_json(_batch_fill_blank("w0"))
    item_id = service.generate(db, owner.id, _request_by_count(5, QuizType.FILL_BLANK))[0].id

    service.answer(db, owner.id, item_id, "w0")
    service.answer(db, owner.id, item_id, "sai rồi")

    assert _count(db, QuizAttempt) == 2
    # So từng dòng, không chỉ đếm: hai lượt phải giữ nguyên câu trả lời KHÁC NHAU của chúng.
    rows = [
        tuple(r)
        for r in db.execute(
            text("SELECT user_answer, correct, score FROM quiz_attempt ORDER BY id")
        )
    ]
    assert rows == [("w0", True, 100), ("sai rồi", False, 0)]


def test_grading_free_write_uses_the_quiz_grade_timeout_tier(
    db: Session, gemini: FakeGemini, owner: UserFixture, timeout_tiers: list[GeminiTimeout]
) -> None:
    """Chấm một bài viết trả về nhiều token hơn hẳn một lượt dịch — dùng nhầm mức TRANSLATE
    (15 giây) là lượt chấm đứt giữa chừng trên máy người dùng, còn test thì vẫn xanh."""
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    item_id = service.generate(db, owner.id, _request_by_count(5, QuizType.FREE_WRITE))[0].id
    gemini.queue_json(_grade_free_write(True, True, True, 80))

    service.answer(db, owner.id, item_id, "I will w0 the risk.")

    assert timeout_tiers == [GeminiTimeout.QUIZ_GRADE]


def test_band_ok_false_does_not_make_the_answer_wrong(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Nhãn band là gợi ý tham khảo, không phải sự thật — trượt band mà dùng từ đúng nghĩa,
    đúng ngữ pháp thì vẫn là đúng. Điểm vẫn giữ nguyên con số Gemini trả."""
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    item_id = service.generate(db, owner.id, _request_by_count(5, QuizType.FREE_WRITE))[0].id
    gemini.queue_json(_grade_free_write(True, True, False, 70))

    result = service.answer(db, owner.id, item_id, "I will w0 the risk.")

    assert result.correct is True
    assert result.score == 70


def test_meaning_ok_false_is_wrong_even_when_grammar_is_correct(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Dùng từ sai nghĩa là hỏng đúng thứ đang được luyện, dù câu viết trơn tru."""
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    item_id = service.generate(db, owner.id, _request_by_count(5, QuizType.FREE_WRITE))[0].id
    gemini.queue_json(_grade_free_write(False, True, True, 30))

    assert service.answer(db, owner.id, item_id, "I ate a w0.").correct is False


def test_gemini_score_outside_the_0_100_range_is_clamped(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Điểm 250 không được lọt ra API — hợp đồng nói 0..100 và panel vẽ thanh điểm theo đó."""
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    item_id = service.generate(db, owner.id, _request_by_count(5, QuizType.FREE_WRITE))[0].id
    gemini.queue_json(_grade_free_write(True, True, True, 250))

    assert service.answer(db, owner.id, item_id, "I will w0 it.").score == 100


def test_answer_not_parseable_as_an_index_is_a_wrong_answer_not_an_error(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Người dùng gõ bậy không phải sự cố hệ thống — ném ở đây biến nó thành HTTP 500.

    Feedback vẫn phải khác rỗng: đó là kênh DUY NHẤT người học biết đáp án, vì `QuizItemDto`
    cố ý không mang nó.
    """
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    gemini.queue_json(
        {
            "items": [
                {
                    "term": "w0",
                    "question": "Cụm nào tự nhiên?",
                    "options": ["a", "b", "c", "d"],
                    "correct_index": 1,
                }
            ]
        }
    )
    item_id = service.generate(db, owner.id, _request_by_count(5, QuizType.COLLOCATION_CHOICE))[
        0
    ].id

    result = service.answer(db, owner.id, item_id, "hai")

    assert result.correct is False
    assert result.score == 0
    assert result.feedback.strip() != ""


def test_answer_longer_than_1000_chars_is_text_too_long_even_for_locally_graded_types(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Giới hạn áp cho MỌI loại, kể cả loại chấm tại chỗ không chạm Gemini.

    Và không được ghi dòng lịch sử nào: request bị từ chối thì nó chưa từng là một lượt làm.
    """
    _srs_card(db, _save_word(db, owner.id, "w0"), 2, 0)
    gemini.queue_json(_batch_fill_blank("w0"))
    item_id = service.generate(db, owner.id, _request_by_count(5, QuizType.FILL_BLANK))[0].id

    with pytest.raises(AppError) as err:
        service.answer(db, owner.id, item_id, "a" * 1001)
    assert err.value.code is ErrorCode.TEXT_TOO_LONG
    assert _count(db, QuizAttempt) == 0


def test_item_that_does_not_exist_gives_not_found(
    db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """NOT_FOUND chứ không FORBIDDEN — 403 xác nhận id đó có tồn tại (ràng buộc #13)."""
    with pytest.raises(AppError) as err:
        service.answer(db, owner.id, 123_456, "x")
    assert err.value.code is ErrorCode.NOT_FOUND
