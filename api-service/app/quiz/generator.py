"""Sinh đề quiz theo LÔ: một lượt gọi Gemini cho cả nhóm từ cùng loại, không phải mỗi từ một
lượt. 10 từ FILL_BLANK = 1 call.

Thứ tự ưu tiên là TÁI DÙNG TRƯỚC, SINH SAU: item cũ còn đúng `prompt_version` và chưa ai làm
thì dùng lại, nên mở lại màn quiz không tốn call nào.
"""

from __future__ import annotations

import logging
import random
from collections import deque
from collections.abc import Sequence
from typing import Any, assert_never

from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.common.gemini import GeminiTimeout, get_gemini_client
from app.quiz import repository, validator
from app.quiz.models import QuizItem, QuizType
from app.quota.guard import consume
from app.translation.prompts import get_prompt_loader
from app.vocabulary.models import VocabEntry

log = logging.getLogger(__name__)

FILL_BLANK_PROMPT = "quiz-fill-blank.md"
COLLOCATION_PROMPT = "quiz-collocation.md"
GRADE_PROMPT = "quiz-grade-free-write.md"

#: Schema structured output cho lô câu điền từ.
FILL_BLANK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "sentence": {"type": "string"},
                    "answer": {"type": "string"},
                    "hint": {"type": "string"},
                },
                "required": ["term", "sentence", "answer", "hint"],
            },
        }
    },
    "required": ["items"],
}

#: Schema structured output cho lô câu chọn collocation.
COLLOCATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "correct_index": {"type": "integer"},
                },
                "required": ["term", "question", "options", "correct_index"],
            },
        }
    },
    "required": ["items"],
}

_random = random.Random()


def prompt_version_for(quiz_type: QuizType) -> int:
    """Version prompt quyết định item loại này còn hiệu lực hay không.

    Đây là nửa còn lại của cơ chế tái dùng: `find_reusable` chỉ nhận item có
    `prompt_version` bằng đúng con số này, nên sửa nội dung một file prompt và tăng
    `version:` ở đầu file là cách DUY NHẤT làm đề cũ hết hiệu lực. Quên tăng version thì
    người dùng nhận đề sinh bằng prompt cũ mãi mãi, không có gì đỏ.
    """
    prompts = get_prompt_loader()
    match quiz_type:
        case QuizType.FILL_BLANK:
            return prompts.load_file(FILL_BLANK_PROMPT).version
        case QuizType.COLLOCATION_CHOICE:
            return prompts.load_file(COLLOCATION_PROMPT).version
        case QuizType.FREE_WRITE:
            # FREE_WRITE không có prompt sinh đề; prompt chấm là thứ duy nhất ảnh hưởng tới
            # loại này, nên tăng version prompt chấm làm đề FREE_WRITE cũ hết hiệu lực.
            return prompts.load_file(GRADE_PROMPT).version
    assert_never(quiz_type)


def build_items(
    db: Session, user_id: int, vocab_ids: Sequence[int], quiz_type: QuizType
) -> list[tuple[QuizItem, VocabEntry]]:
    """Dựng đề cho ĐÚNG MỘT loại. Một loại mỗi lượt là hình dạng của endpoint
    `POST /api/quiz/generate` — gộp nhiều loại đẩy trường hợp xấu nhất lên gấp đôi và biến
    một loại hỏng thành mất trắng cả đề.

    Trả item theo đúng thứ tự `vocab_ids`, kèm từ gốc; từ nào Gemini trả về hỏng thì vắng
    mặt. Rỗng khi không có từ nào hợp lệ để hỏi.

    Ném `PARSE_ERROR` khi có từ để hỏi mà không dựng nổi item nào — trả mảng rỗng lúc đó là
    giả vờ thành công.
    """
    entries = repository.find_owned_entries_in_order(db, user_id, vocab_ids)
    if not entries:
        return []

    prompt_version = prompt_version_for(quiz_type)
    theo_tu = _reusable_by_entry(db, user_id, entries, quiz_type, prompt_version)

    can_sinh = [entry for entry in entries if entry.id not in theo_tu]
    if can_sinh:
        theo_tu.update(_generate(db, user_id, can_sinh, quiz_type, prompt_version))

    ket_qua = [(theo_tu[entry.id], entry) for entry in entries if entry.id in theo_tu]
    if not ket_qua:
        raise AppError.of(
            ErrorCode.PARSE_ERROR, "Gemini không trả được câu hỏi nào hợp lệ, thử tạo đề lại"
        )
    return ket_qua


def _reusable_by_entry(
    db: Session,
    user_id: int,
    entries: Sequence[VocabEntry],
    quiz_type: QuizType,
    prompt_version: int,
) -> dict[int, QuizItem]:
    """Mỗi từ lấy tối đa MỘT item tái dùng.

    `find_reusable` sắp theo `id` tăng dần, nên "cái đầu tiên gặp" là item CŨ NHẤT còn hiệu
    lực — đề đã nằm sẵn đó lâu nhất được dùng trước, thay vì để nó tồn đọng mãi.
    """
    ids = [entry.id for entry in entries]
    theo_tu: dict[int, QuizItem] = {}
    for item in repository.find_reusable(db, user_id, ids, [quiz_type], prompt_version):
        theo_tu.setdefault(item.vocab_entry_id, item)
    return theo_tu


def _generate(
    db: Session,
    user_id: int,
    entries: Sequence[VocabEntry],
    quiz_type: QuizType,
    prompt_version: int,
) -> dict[int, QuizItem]:
    match quiz_type:
        case QuizType.FREE_WRITE:
            # FREE_WRITE dựng thẳng ở Python, KHÔNG gọi Gemini nên không tính hạn mức.
            return _build_free_write(db, entries, prompt_version)
        case QuizType.FILL_BLANK:
            return _call_gemini(
                db,
                user_id,
                entries,
                quiz_type,
                prompt_version,
                FILL_BLANK_PROMPT,
                FILL_BLANK_SCHEMA,
            )
        case QuizType.COLLOCATION_CHOICE:
            return _call_gemini(
                db,
                user_id,
                entries,
                quiz_type,
                prompt_version,
                COLLOCATION_PROMPT,
                COLLOCATION_SCHEMA,
            )
    assert_never(quiz_type)


def _build_free_write(
    db: Session, entries: Sequence[VocabEntry], prompt_version: int
) -> dict[int, QuizItem]:
    """FREE_WRITE dựng thẳng từ sổ từ — không tốn call Gemini nào lúc sinh đề."""
    da_dung: dict[int, QuizItem] = {}
    for entry in entries:
        payload = {
            "question": f'Viết một câu tiếng Anh dùng từ "{entry.term}" '
            f"({_none_to_empty(entry.meaning_vi)})."
        }
        da_dung[entry.id] = _save(db, entry, QuizType.FREE_WRITE, payload, prompt_version)
    return da_dung


def _call_gemini(
    db: Session,
    user_id: int,
    entries: Sequence[VocabEntry],
    quiz_type: QuizType,
    prompt_version: int,
    prompt_file: str,
    schema: dict[str, Any],
) -> dict[int, QuizItem]:
    template = get_prompt_loader().load_file(prompt_file)
    prompt = template.render({"TERMS": _render_terms(entries)})
    consume(db, user_id)
    payload = get_gemini_client().generate_json(prompt, schema, GeminiTimeout.QUIZ_GENERATE)

    # Ghép item Gemini trả về với từ trong sổ bằng chính field `term`. Deque vì hai bản ghi
    # khác pos vẫn có thể trùng term ("record" danh từ và động từ).
    cho_ghep: dict[str, deque[VocabEntry]] = {}
    for entry in entries:
        cho_ghep.setdefault(_normalise(entry.term), deque()).append(entry)

    da_dung: dict[int, QuizItem] = {}
    for node in _items_of(payload):
        term = _opt_str(node, "term") or ""
        hang_doi = cho_ghep.get(_normalise(term))
        if not hang_doi:
            log.warning("Gemini trả câu hỏi cho từ không nằm trong lô: '%s'", term)
            continue
        entry = hang_doi[0]
        item_payload = _to_payload(quiz_type, node)
        if item_payload is None:
            # Loại TỪNG item hỏng rồi đi tiếp — khác bộ kiểm mồi nhử (loại cả bộ). Người dùng
            # đang đứng chờ; bắt họ đợi thêm một lượt Gemini vì một câu hỏng là đắt vô lý,
            # còn 9 câu kia vẫn dùng được.
            log.warning("Bỏ câu hỏi %s hỏng cho từ '%s'", quiz_type.value, entry.term)
            continue
        hang_doi.popleft()
        da_dung[entry.id] = _save(db, entry, quiz_type, item_payload, prompt_version)
    return da_dung


def _to_payload(quiz_type: QuizType, node: dict[str, Any]) -> dict[str, Any] | None:
    """Payload hợp lệ để lưu, hoặc None nếu item hỏng."""
    match quiz_type:
        case QuizType.FILL_BLANK:
            return _fill_blank_payload(node)
        case QuizType.COLLOCATION_CHOICE:
            return _collocation_payload(node)
        case QuizType.FREE_WRITE:
            # FREE_WRITE không bao giờ đi qua Gemini lúc sinh đề.
            return None
    assert_never(quiz_type)


def _fill_blank_payload(node: dict[str, Any]) -> dict[str, Any] | None:
    sentence = _opt_str(node, "sentence")
    answer = _opt_str(node, "answer")
    hint = _opt_str(node, "hint")
    if not validator.is_valid_fill_blank(sentence, answer, hint):
        return None
    return {"sentence": sentence, "answer": answer, "hint": hint}


def _collocation_payload(node: dict[str, Any]) -> dict[str, Any] | None:
    raw = node.get("options")
    options: list[str | None] = (
        [tung_cum if isinstance(tung_cum, str) else None for tung_cum in raw]
        if isinstance(raw, list)
        else []
    )
    correct_index = _opt_int(node, "correct_index")
    if not validator.is_valid_collocation(options, correct_index):
        return None
    # Qua được validator nghĩa là: đúng 4 lựa chọn, không phần tử None, index trong 0..3.
    # Hai dòng thu hẹp kiểu dưới đây chỉ để mypy biết điều đó, không phải kiểm tra thứ hai.
    assert correct_index is not None
    da_xao = [cum for cum in options if cum is not None]
    cum_dung = da_xao[correct_index]

    # Xáo ĐÚNG MỘT LẦN, ngay tại đây. Gemini có xu hướng đặt đáp án đúng ở vị trí 0 nên giữ
    # nguyên thứ tự của nó là làm quiz đoán được mà không cần biết từ. Sau dòng này thứ tự là
    # bất biến: không xáo lúc dựng response, panel không xáo — câu trả lời gửi lên là index
    # trong CHÍNH mảng đang lưu ở đây.
    _random.shuffle(da_xao)

    return {
        "question": _opt_str(node, "question") or "",
        "options": da_xao,
        "correct_index": da_xao.index(cum_dung),
    }


def _save(
    db: Session,
    entry: VocabEntry,
    quiz_type: QuizType,
    payload: dict[str, Any],
    prompt_version: int,
) -> QuizItem:
    item = QuizItem(
        vocab_entry_id=entry.id,
        type=quiz_type.value,
        payload=payload,
        prompt_version=prompt_version,
    )
    return repository.save_item(db, item)


def _render_terms(entries: Sequence[VocabEntry]) -> str:
    """Mỗi từ một dòng: `term | pos | nghĩa tiếng Việt`."""
    return "\n".join(
        f"{_none_to_empty(entry.term)} | {_none_to_empty(entry.pos)} | "
        f"{_none_to_empty(entry.meaning_vi)}"
        for entry in entries
    ).strip()


def _items_of(payload: Any) -> list[dict[str, Any]]:
    """Mảng `items` trong phản hồi Gemini; thiếu hoặc sai kiểu thì coi như rỗng."""
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return [node for node in items if isinstance(node, dict)]


def _opt_str(node: dict[str, Any], key: str) -> str | None:
    """None khi thiếu khoá HOẶC giá trị không phải chuỗi.

    Bản Java gọi `asText(null)`, vốn tự ép số thành chuỗi. Ở đây chặt hơn: giá trị sai kiểu
    làm item bị loại thay vì lẳng lặng biến thành "123". Schema đã khai `string`, nên sai
    kiểu là dấu hiệu model trả rác chứ không phải chuyện cần chiều.
    """
    value = node.get(key)
    return value if isinstance(value, str) else None


def _opt_int(node: dict[str, Any], key: str) -> int | None:
    """None khi thiếu khoá hoặc không phải số nguyên. `bool` bị loại: trong Python `True` là
    một `int` hợp lệ, và `correct_index = true` sẽ lặng lẽ thành index 1."""
    value = node.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def payload_str(value: Any) -> str:
    """Đọc một field chuỗi trong `quiz_item.payload`. None → chuỗi rỗng.

    Ba hàm `payload_*` đặt ở đây, cạnh chỗ GHI payload, để hình dạng payload chỉ có một nơi
    phải nhớ. `service.py` và `explain.py` là hai chỗ đọc.
    """
    return "" if value is None else str(value)


def payload_str_list(value: Any) -> list[str]:
    """Đọc `payload.options`. Giữ NGUYÊN độ dài và thứ tự kể cả khi có phần tử sai kiểu:
    `correct_index` trỏ vào chính mảng này, lọc bớt một phần tử là chấm sai câu đó."""
    if not isinstance(value, list):
        return []
    return [cum if isinstance(cum, str) else str(cum) for cum in value]


def payload_int(value: Any) -> int:
    """Đọc `payload.correct_index`. Không phải số → -1, tức "không index nào khớp"."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return -1
    return int(value)


def _normalise(value: str | None) -> str:
    return "" if value is None else value.strip().lower()


def _none_to_empty(value: str | None) -> str:
    return "" if value is None else value
