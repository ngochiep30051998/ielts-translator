"""Điều phối ba luồng quiz: sinh đề, chấm bài, giải thích.

Ba loại chấm theo ba đường khác nhau: FILL_BLANK và COLLOCATION_CHOICE chấm tại chỗ (100 hoặc
0, không chạm Gemini), FREE_WRITE do Gemini chấm (0–100).
"""

from __future__ import annotations

from typing import Any, assert_never

from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.common.gemini import GeminiTimeout, get_gemini_client
from app.quiz import candidates, generator, grader, repository
from app.quiz import explain as explain_module
from app.quiz.generator import payload_int, payload_str, payload_str_list
from app.quiz.models import (
    AnswerResultDto,
    ExplanationDto,
    GenerateQuizRequest,
    QuizAttempt,
    QuizItem,
    QuizItemDto,
    QuizType,
)
from app.quota.guard import consume
from app.translation.prompts import get_prompt_loader
from app.vocabulary.models import VocabEntry

#: Giới hạn cứng phía server; QuizTab phía extension cũng chặn ở CÙNG con số.
MAX_ANSWER_LENGTH = 1000

GRADE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "meaning_ok": {"type": "boolean"},
        "grammar_ok": {"type": "boolean"},
        "band_ok": {"type": "boolean"},
        "score": {"type": "integer"},
        "feedback_vi": {"type": "string"},
        "improved_version": {"type": "string"},
    },
    "required": ["meaning_ok", "grammar_ok", "band_ok", "score", "feedback_vi"],
}


def generate(db: Session, user_id: int, request: GenerateQuizRequest) -> list[QuizItemDto]:
    """Trả MẢNG RỖNG khi không có ứng viên — đó là trạng thái "chưa ôn từ nào đủ điều kiện",
    không phải lỗi. Ném ở đây sẽ buộc phải đẻ thêm một ErrorCode cho một tình huống hoàn toàn
    bình thường.
    """
    if request.vocab_ids:
        # `vocab_ids` đến THẲNG từ client. `build_items` nạp từ theo (id, user_id) nên id của
        # người khác rơi ra ngay ở câu truy vấn — không lọc thì người dùng đặt tay id của
        # người khác vào và nhận về đề chứa term + câu ví dụ trong sổ từ của họ.
        vocab_ids = request.vocab_ids
    elif request.count is not None:
        vocab_ids = candidates.find_candidates(db, user_id, request.count)
    else:  # validator của GenerateQuizRequest đã loại; nhánh này chỉ để kiểu luôn xác định
        vocab_ids = []

    if not vocab_ids:
        return []

    return [
        _to_dto(item, entry)
        for item, entry in generator.build_items(db, user_id, vocab_ids, request.type)
    ]


def answer(db: Session, user_id: int, quiz_item_id: int, given: str) -> AnswerResultDto:
    # Chặn độ dài TRƯỚC cả khi tra item, và chặn thủ công thay vì bằng ràng buộc trên DTO, để
    # ném TEXT_TOO_LONG (400, đúng ngữ nghĩa) thay vì INTERNAL (500).
    if len(given) > MAX_ANSWER_LENGTH:
        raise AppError.of(
            ErrorCode.TEXT_TOO_LONG, f"Bài viết quá dài (tối đa {MAX_ANSWER_LENGTH} ký tự)"
        )

    cap = repository.find_owned_item(db, quiz_item_id, user_id)
    if cap is None:
        raise AppError.of(ErrorCode.NOT_FOUND, f"Không tìm thấy câu hỏi id={quiz_item_id}")
    item, entry = cap

    if not given.strip():
        # Bỏ qua câu: chấm 0 và ghi lịch sử như một lượt làm THẬT. Không ghi thì item vẫn lọt
        # `find_reusable` và câu đã bỏ qua sẽ hiện lại ở đề sau như chưa từng làm. KHÔNG gọi
        # Gemini — chấm một bài viết rỗng là đốt quota để nhận về một lời chê hiển nhiên.
        return _record(db, item, given, False, 0, "Chưa trả lời.", None)

    quiz_type = QuizType(item.type)
    match quiz_type:
        case QuizType.FILL_BLANK:
            return _grade_fill_blank(db, item, given)
        case QuizType.COLLOCATION_CHOICE:
            return _grade_collocation(db, item, given)
        case QuizType.FREE_WRITE:
            return _grade_free_write(db, user_id, item, entry, given)
    assert_never(quiz_type)


def explain(db: Session, user_id: int, quiz_item_id: int) -> ExplanationDto:
    """Luồng giải thích nằm trọn trong `explain.py` vì nó có tập prompt, schema và bộ dựng đầu
    vào riêng cho từng loại — đủ lớn để đứng một mình. Router vẫn đi qua service cho cả ba
    endpoint."""
    return explain_module.explain(db, user_id, quiz_item_id)


def _grade_fill_blank(db: Session, item: QuizItem, given: str) -> AnswerResultDto:
    expected = payload_str(item.payload.get("answer"))
    correct = grader.grade_fill_blank(given, expected)
    # Khi sai, feedback CHỨA LUÔN đáp án đúng — QuizItemDto cố ý không mang nó, nên đây là
    # kênh duy nhất người học biết đáp án.
    return _record(
        db,
        item,
        given,
        correct,
        100 if correct else 0,
        "Chính xác." if correct else f"Chưa đúng. Đáp án: {expected}",
        None,
    )


def _grade_collocation(db: Session, item: QuizItem, given: str) -> AnswerResultDto:
    options = payload_str_list(item.payload.get("options"))
    correct_index = payload_int(item.payload.get("correct_index"))
    correct = grader.grade_collocation(given, correct_index)
    cum_dung = options[correct_index] if 0 <= correct_index < len(options) else ""
    return _record(
        db,
        item,
        given,
        correct,
        100 if correct else 0,
        "Chính xác." if correct else f"Chưa đúng. Đáp án: {cum_dung}",
        None,
    )


def _grade_free_write(
    db: Session, user_id: int, item: QuizItem, entry: VocabEntry, given: str
) -> AnswerResultDto:
    consume(db, user_id)
    template = get_prompt_loader().load_file(generator.GRADE_PROMPT)
    prompt = template.render(
        {
            "TERM": _none_to_empty(entry.term),
            "POS": _none_to_empty(entry.pos),
            "MEANING_VI": _none_to_empty(entry.meaning_vi),
            "DEFINITION_EN": _none_to_empty(entry.definition_en),
            "ANSWER": given,
        }
    )

    payload = get_gemini_client().generate_json(prompt, GRADE_SCHEMA, GeminiTimeout.QUIZ_GRADE)

    # band_ok CỐ Ý không tham gia vào `correct`: nhãn band là gợi ý tham khảo, không phải sự
    # thật — trượt band mà dùng từ đúng nghĩa, đúng ngữ pháp thì vẫn là đúng.
    correct = _flag(payload, "meaning_ok") and _flag(payload, "grammar_ok")
    score = max(0, min(100, _score(payload)))
    feedback = _text(payload, "feedback_vi")
    if not feedback.strip():
        feedback = "Câu dùng từ hợp lý." if correct else "Câu chưa đạt, xem lại cách dùng từ."
    improved = _text(payload, "improved_version")
    return _record(
        db, item, given, correct, score, feedback, improved if improved.strip() else None
    )


def _record(
    db: Session,
    item: QuizItem,
    given: str,
    correct: bool,
    score: int,
    feedback: str,
    improved_version: str | None,
) -> AnswerResultDto:
    """Ghi một lượt làm bài rồi trả kết quả. Mọi đường chấm đều phải đi qua đây — bỏ sót một
    đường là câu đó không bao giờ được coi là đã làm, nên nó vẫn lọt `find_reusable` và quay
    lại ở đề sau."""
    repository.save_attempt(
        db,
        QuizAttempt(
            quiz_item_id=item.id,
            user_answer=given,
            correct=correct,
            score=score,
            ai_feedback=feedback,
            improved_version=improved_version,
        ),
    )
    return AnswerResultDto(
        correct=correct, score=score, feedback=feedback, improved_version=improved_version
    )


def _to_dto(item: QuizItem, entry: VocabEntry) -> QuizItemDto:
    """Điểm nghẽn duy nhất giữa payload (CÓ đáp án) và HTTP (KHÔNG có đáp án). Mọi field đều
    lấy tường minh từ payload; KHÔNG bao giờ đổ nguyên payload vào DTO."""
    payload = item.payload
    quiz_type = QuizType(item.type)
    match quiz_type:
        case QuizType.FILL_BLANK:
            # term = None: với FILL_BLANK, term CHÍNH LÀ đáp án. Gửi kèm là lộ đáp án dù
            # payload.answer không nằm trong DTO.
            return QuizItemDto(
                id=item.id,
                type=quiz_type,
                vocab_entry_id=item.vocab_entry_id,
                term=None,
                question="Điền từ còn thiếu vào chỗ trống. Gợi ý: "
                + payload_str(payload.get("hint")),
                sentence=payload_str(payload.get("sentence")),
                options=None,
            )
        case QuizType.COLLOCATION_CHOICE:
            # options giữ NGUYÊN thứ tự đã lưu — đã xáo một lần lúc sinh item rồi.
            return QuizItemDto(
                id=item.id,
                type=quiz_type,
                vocab_entry_id=item.vocab_entry_id,
                term=entry.term,
                question=payload_str(payload.get("question")),
                sentence=None,
                options=payload_str_list(payload.get("options")),
            )
        case QuizType.FREE_WRITE:
            return QuizItemDto(
                id=item.id,
                type=quiz_type,
                vocab_entry_id=item.vocab_entry_id,
                term=entry.term,
                question=payload_str(payload.get("question")),
                sentence=None,
                options=None,
            )
    assert_never(quiz_type)


def _flag(payload: Any, key: str) -> bool:
    """Cờ boolean trong phản hồi Gemini; thiếu hoặc sai kiểu thì coi như false.

    Chỉ nhận đúng `True`: bản Java gọi `asBoolean(false)`, vốn cũng coi số khác 0 và chuỗi
    "true" là đúng. Ở đây chặt hơn vì đây là chỗ quyết định bài đúng hay sai — đoán ý model
    khi nó trả sai kiểu là chấm bằng may rủi.
    """
    return isinstance(payload, dict) and payload.get(key) is True


def _score(payload: Any) -> int:
    """Điểm thô Gemini trả; thiếu hoặc sai kiểu thì 0. Nhận cả số thực vì JSON không phân biệt
    85 với 85.0."""
    value = payload.get("score") if isinstance(payload, dict) else None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    return int(value)


def _text(payload: Any, key: str) -> str:
    if not isinstance(payload, dict):
        return ""
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _none_to_empty(value: str | None) -> str:
    return "" if value is None else value
