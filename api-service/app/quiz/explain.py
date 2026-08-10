"""Giải thích một câu ĐÃ trả lời. KHÔNG ghi gì xuống DB.

Response ở đây TIẾT LỘ ĐÁP ÁN, nên endpoint chỉ phục vụ item đã có lượt làm. Hai chốt chặn
nằm cạnh nhau và đều TRƯỚC lượt gọi Gemini:

1. item phải thuộc về chính user (rò ở đây vừa là rò dữ liệu vừa là đốt quota của người
   khác);
2. item phải có ít nhất một `quiz_attempt`.

`ExplainQuizRequest` cố ý không nhận câu trả lời từ client: tin câu trả lời client gửi lên là
biến `/explain` thành đường vòng đọc đáp án trước khi trả lời.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, assert_never

from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.common.gemini import GeminiTimeout, get_gemini_client
from app.quiz import repository
from app.quiz.generator import payload_int, payload_str, payload_str_list
from app.quiz.models import ExplanationDto, QuizAttempt, QuizItem, QuizType
from app.quota.guard import consume
from app.translation.prompts import get_prompt_loader
from app.vocabulary.models import VocabEntry

FILL_BLANK_PROMPT = "quiz-explain-fill-blank.md"
COLLOCATION_PROMPT = "quiz-explain-collocation.md"
FREE_WRITE_PROMPT = "quiz-explain-free-write.md"

#: CHỈ hai field bắt buộc, và đó là chủ ý.
#:
#: `sentence_en` không bắt buộc vì hai trong ba loại backend đã tự biết câu tiếng Anh — nhờ
#: Gemini chép lại một chuỗi đang cầm trong tay là mời nó chép sai. `sentence_vi` không bắt
#: buộc vì có đúng một ca không tồn tại câu nào để dịch (FREE_WRITE bị bỏ qua); bắt buộc field
#: đó là ép Gemini bịa ra một câu tiếng Việt không gắn với câu tiếng Anh nào.
EXPLAIN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "explanation_vi": {"type": "string"},
        "answer_meaning_vi": {"type": "string"},
        "sentence_en": {"type": "string"},
        "sentence_vi": {"type": "string"},
    },
    "required": ["explanation_vi", "answer_meaning_vi"],
}


@dataclass(frozen=True)
class ExplainInput:
    """Đầu vào đã chuẩn hoá cho một lượt giải thích.

    `known_sentence_en` là câu tiếng Anh backend đã biết. RỖNG nghĩa là backend không có câu
    nào — hoặc vì loại đó cần Gemini nghĩ ra (COLLOCATION_CHOICE), hoặc vì thật sự không có
    câu nào tồn tại (FREE_WRITE bị bỏ qua). Cả hai ca đều xử lý giống nhau: lấy `sentence_en`
    Gemini trả, rỗng thì bỏ cả cặp.
    """

    prompt_file: str
    vars: dict[str, str]
    known_sentence_en: str


def explain(db: Session, user_id: int, quiz_item_id: int) -> ExplanationDto:
    cap = repository.find_owned_item(db, quiz_item_id, user_id)
    if cap is None:
        raise AppError.of(ErrorCode.NOT_FOUND, f"Không tìm thấy câu hỏi id={quiz_item_id}")
    item, entry = cap

    attempt = repository.find_latest_attempt(db, quiz_item_id, user_id)
    if attempt is None:
        raise AppError.of(ErrorCode.NOT_FOUND, "Chưa trả lời câu này nên chưa có gì để giải thích")

    quiz_type = QuizType(item.type)
    match quiz_type:
        case QuizType.FILL_BLANK:
            dau_vao = _fill_blank_input(item, entry, attempt)
        case QuizType.COLLOCATION_CHOICE:
            dau_vao = _collocation_input(item, entry, attempt)
        case QuizType.FREE_WRITE:
            dau_vao = _free_write_input(entry, attempt)
        case _:
            assert_never(quiz_type)

    consume(db, user_id)
    template = get_prompt_loader().load_file(dau_vao.prompt_file)
    payload = get_gemini_client().generate_json(
        template.render(dau_vao.vars), EXPLAIN_SCHEMA, GeminiTimeout.QUIZ_GRADE
    )

    explanation = _first_non_blank(
        _text(payload, "explanation_vi"), "Chưa lấy được giải thích cho câu này."
    )
    answer_meaning = _first_non_blank(
        _text(payload, "answer_meaning_vi"), _meaning_from_vocab(entry), "(chưa có nghĩa)"
    )

    # `known_sentence_en` khác rỗng nghĩa là BACKEND biết câu tiếng Anh; lúc đó chuỗi Gemini
    # trả về bị bỏ qua hoàn toàn.
    sentence_en: str | None = (
        _text(payload, "sentence_en")
        if not dau_vao.known_sentence_en.strip()
        else dau_vao.known_sentence_en
    )
    sentence_vi: str | None = _text(payload, "sentence_vi")
    # Thiếu một nửa thì bỏ cả cặp. Trả một nửa là bắt panel render khối "Dịch câu" với đúng
    # một dòng trống.
    if not (sentence_en or "").strip() or not (sentence_vi or "").strip():
        sentence_en = None
        sentence_vi = None

    return ExplanationDto(
        explanation=explanation,
        answer_meaning=answer_meaning,
        sentence_en=sentence_en,
        sentence_vi=sentence_vi,
    )


def _fill_blank_input(item: QuizItem, entry: VocabEntry, attempt: QuizAttempt) -> ExplainInput:
    sentence = payload_str(item.payload.get("sentence"))
    answer = payload_str(item.payload.get("answer"))
    # Câu đã điền đáp án ghép ở đây chứ không nhờ Gemini. Prompt sinh đề đã bảo đảm "___"
    # xuất hiện đúng một lần trong câu.
    da_dien = sentence.replace("___", answer)
    return ExplainInput(
        FILL_BLANK_PROMPT,
        {
            "SENTENCE": sentence,
            "ANSWER": answer,
            "TERM": _none_to_empty(entry.term),
            "POS": _none_to_empty(entry.pos),
            "MEANING_VI": _none_to_empty(entry.meaning_vi),
            "USER_ANSWER": _none_to_empty(attempt.user_answer),
        },
        da_dien,
    )


def _collocation_input(item: QuizItem, entry: VocabEntry, attempt: QuizAttempt) -> ExplainInput:
    options = payload_str_list(item.payload.get("options"))
    correct_index = payload_int(item.payload.get("correct_index"))
    cum_dung = options[correct_index] if 0 <= correct_index < len(options) else ""
    danh_sach = "\n".join(f"{i + 1}. {cum}" for i, cum in enumerate(options)).strip()

    return ExplainInput(
        COLLOCATION_PROMPT,
        {
            "TERM": _none_to_empty(entry.term),
            "POS": _none_to_empty(entry.pos),
            "MEANING_VI": _none_to_empty(entry.meaning_vi),
            "QUESTION": payload_str(item.payload.get("question")),
            "OPTIONS": danh_sach,
            "ANSWER": cum_dung,
            # Câu trả lời lưu trong attempt là INDEX dạng chuỗi. Dịch ngược ra nội dung cụm
            # ngay tại đây: đưa "2" vào prompt thì Gemini không biết người học đã chọn gì.
            "USER_ANSWER": _option_at(options, _none_to_empty(attempt.user_answer)),
        },
        "",
    )


def _free_write_input(entry: VocabEntry, attempt: QuizAttempt) -> ExplainInput:
    user_answer = _none_to_empty(attempt.user_answer)
    # Câu viết lại là câu mẫu đáng học nhất; không có thì lấy chính câu người học. Bỏ qua câu
    # thì cả hai đều rỗng — lúc đó KHÔNG có câu nào để dịch, và cặp sentence_en/sentence_vi sẽ
    # cùng về None ở chỗ ghép kết quả.
    sentence_en = _first_non_blank(_none_to_empty(attempt.improved_version), user_answer)
    return ExplainInput(
        FREE_WRITE_PROMPT,
        {
            "TERM": _none_to_empty(entry.term),
            "POS": _none_to_empty(entry.pos),
            "MEANING_VI": _none_to_empty(entry.meaning_vi),
            "DEFINITION_EN": _none_to_empty(entry.definition_en),
            "USER_ANSWER": user_answer,
            "SENTENCE_EN": sentence_en,
        },
        sentence_en,
    )


def _option_at(options: list[str], raw_index: str) -> str:
    """Chuỗi không parse được thành index hợp lệ — kể cả rỗng, tức bỏ qua — trả chuỗi rỗng.

    Trả `options[0]` ở nhánh không parse được là sai và sai âm thầm: bỏ qua câu lưu
    `user_answer = ""`, nên prompt sẽ nói "Người học đã chọn: <cụm số 0>" và Gemini giải
    thích một lựa chọn người học chưa từng bấm. Chuỗi rỗng là thứ prompt đang chờ — nó có
    sẵn nhánh "nếu người học bỏ qua thì chỉ giải thích đáp án".
    """
    try:
        index = int(raw_index.strip())
    except ValueError:
        return ""
    return options[index] if 0 <= index < len(options) else ""


def _meaning_from_vocab(entry: VocabEntry) -> str:
    """Nghĩa lấy từ chính sổ từ của người dùng, làm lưới hứng khi Gemini trả rỗng."""
    if entry.meaning_vi is None or not entry.meaning_vi.strip():
        return ""
    return f"{entry.term} = {entry.meaning_vi}"


def _first_non_blank(*values: str | None) -> str:
    """Giá trị đầu tiên khác rỗng; hết sạch thì trả chuỗi rỗng."""
    for value in values:
        if value is not None and value.strip():
            return value
    return ""


def _text(payload: Any, key: str) -> str:
    """Field chuỗi trong phản hồi Gemini; thiếu hoặc sai kiểu thì coi như rỗng."""
    if not isinstance(payload, dict):
        return ""
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _none_to_empty(value: str | None) -> str:
    return "" if value is None else value
