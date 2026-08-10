"""Sinh mồi nhử cho câu trắc nghiệm ôn tập, và kiểm bộ mồi nhử Gemini trả về.

Vì sao KHÔNG gộp vào `card_creator`: creator chạy đồng bộ trong cùng transaction với lệnh
lưu từ. Gọi Gemini ở đó sẽ làm thao tác lưu treo tới 15 giây, và Gemini lỗi sẽ kéo đổ luôn
việc lưu từ. Ở đây phải chạy SAU khi response đã trả (từ đã nằm chắc trong sổ) và không ai
đứng chờ kết quả.

Bên Java là `@TransactionalEventListener(AFTER_COMMIT)` + `@Async` với một pool nhỏ. Ở
FastAPI vai trò đó do `BackgroundTasks` đảm nhiệm, và tác vụ nền PHẢI tự mở session riêng
giống hệt việc thread `@Async` bên Java có transaction riêng.

Nhưng `BackgroundTasks` KHÔNG tự cho ta `AFTER_COMMIT`, và đây là chỗ dễ sai nhất của cả
module. Trong `fastapi/routing.py`, lời gọi `await response(scope, receive, send)` — chính
là chỗ Starlette chạy background task — nằm BÊN TRONG `async with AsyncExitStack() as
request_stack`, mà `request_stack` cũng là nơi các dependency kiểu `yield` (tức `get_db`)
đăng ký phần dọn dẹp của mình. Thứ tự thật vì thế là: gửi response → **chạy background
task** → `get_db` commit. Tác vụ nền chạy TRƯỚC khi transaction của request được commit.

Hệ quả nếu quên: session riêng của tác vụ nền không thấy từ vừa lưu, `find_vocab_entry`
trả None, hàm return êm ru — không exception, không log, không test nào đỏ, chỉ là mồi nhử
không bao giờ được sinh ở luồng lưu từ. Vì vậy `schedule()` nhận luôn session của request
và commit nó trước khi xếp việc.
"""

from __future__ import annotations

import logging
import threading
from functools import lru_cache
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.common.gemini import GeminiClient, GeminiTimeout, get_gemini_client
from app.config import API_SERVICE_ROOT
from app.db import get_session_factory
from app.srs import repository as repo
from app.srs.models import DistractorSet, SrsDistractor
from app.vocabulary.models import VocabEntry

log = logging.getLogger(__name__)

#: pos của một câu đầy đủ — câu không làm trắc nghiệm được.
PHRASE_POS = "phrase"
PROMPT_FILE = "srs-distractors.md"
REQUIRED_COUNT = 3

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "vi_options": {"type": "array", "items": {"type": "string"}},
        "en_options": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["vi_options", "en_options"],
}

#: Chặn xếp chồng call cho cùng một từ khi người dùng mở tab ôn nhiều lần.
#: Chỉ có tác dụng trong PHẠM VI MỘT tiến trình — y như `ConcurrentHashMap.newKeySet()` bên
#: Java. Hai instance serverless chạy song song vẫn có thể sinh trùng; chi phí là một lượt
#: gọi Gemini thừa, không phải dữ liệu sai (ghi đè theo `vocab_entry_id` là idempotent).
_in_flight: set[int] = set()
_in_flight_lock = threading.Lock()


def current_prompt_version() -> int:
    return _load_prompt()[1]


def schedule(tasks: BackgroundTasks, db: Session, vocab_entry_id: int) -> None:
    """Xếp một lượt sinh mồi nhử chạy sau khi response đã trả về cho client.

    Context vocabulary gọi hàm này ngay sau khi lưu một từ mới; `service.due` gọi nó cho
    những thẻ còn thiếu mồi nhử.

    `db.commit()` ở đây LÀ phần "AFTER_COMMIT" của bản Java, không phải một dòng thừa:
    background task của FastAPI chạy TRƯỚC khi dependency `get_db` commit (xem docstring
    đầu module). Không commit thì tác vụ nền mở session riêng và không thấy từ vừa lưu —
    hỏng im lặng, không có gì đỏ. Ở đường `service.due` thì session chỉ đang đọc nên commit
    là vô hại; `expire_on_commit=False` giữ nguyên các entity đã nạp.
    """
    db.commit()
    tasks.add_task(generate_distractors, vocab_entry_id)


def generate_distractors(vocab_entry_id: int, client: GeminiClient | None = None) -> None:
    """Điểm vào của tác vụ nền. Tự mở session riêng, tự nuốt lỗi.

    Bắt luôn `Exception` chứ không riêng `AppError`: không ai đang đứng chờ việc này, mà một
    lỗi bay ra khỏi background task chỉ đọng lại trong log của server dưới dạng traceback
    trần. Log rồi thôi — lần mở tab ôn sau sẽ thử lại qua đường `request_missing`.
    """
    if not _claim(vocab_entry_id):
        return

    session = get_session_factory()()
    try:
        entry = repo.find_vocab_entry(session, vocab_entry_id)
        if entry is not None:
            _generate_for(session, entry, client or get_gemini_client())
            session.commit()
    except Exception as ex:
        session.rollback()
        log.warning("Không sinh được mồi nhử cho vocab id=%s: %s", vocab_entry_id, ex)
    finally:
        session.close()
        _release(vocab_entry_id)


def is_valid(options: DistractorSet, meaning_vi: str | None, term: str | None) -> bool:
    """Loại CẢ bộ khi có bất kỳ vi phạm nào, thay vì cố vá từng phần tử.

    Bộ đã hỏng thì phần còn lại cũng không đáng tin, và để lần sau sinh lại rẻ hơn nhiều so
    với việc người học gặp một câu hỏi có hai đáp án cùng đúng.
    """
    return _side_is_valid(options.vi_options, meaning_vi) and _side_is_valid(
        options.en_options, term
    )


def _generate_for(db: Session, entry: VocabEntry, client: GeminiClient) -> None:
    if entry.pos == PHRASE_POS:
        return

    body, version = _load_prompt()
    prompt = _render(
        body,
        {
            "TERM": entry.term or "",
            "POS": entry.pos or "",
            "MEANING_VI": entry.meaning_vi or "",
            "DEFINITION_EN": entry.definition_en or "",
        },
    )

    # TRANSLATE (15s) chứ không phải QUIZ_GENERATE: đây là call nhỏ chạy nền, không ai đứng
    # chờ. Khác mức với quiz cũng là thứ cho phép test quiz đếm call theo mức timeout mà
    # không lẫn với luồng sinh mồi nhử.
    payload = client.generate_json(prompt, SCHEMA, GeminiTimeout.TRANSLATE)
    options = DistractorSet(
        vi_options=_read_strings(_field(payload, "vi_options")),
        en_options=_read_strings(_field(payload, "en_options")),
    )

    if not is_valid(options, entry.meaning_vi, entry.term):
        log.warning("Gemini trả bộ mồi nhử không hợp lệ cho '%s', bỏ qua", entry.term)
        return

    row = repo.find_distractor_by_vocab(db, entry.id)
    if row is None:
        row = SrsDistractor(vocab_entry_id=entry.id)
        db.add(row)
    row.vi_options = options.vi_options
    row.en_options = options.en_options
    row.prompt_version = version
    db.flush()


def _claim(vocab_entry_id: int) -> bool:
    with _in_flight_lock:
        if vocab_entry_id in _in_flight:
            return False
        _in_flight.add(vocab_entry_id)
        return True


def _release(vocab_entry_id: int) -> None:
    with _in_flight_lock:
        _in_flight.discard(vocab_entry_id)


def _side_is_valid(options: list[str], correct_answer: str | None) -> bool:
    """Một chiều hợp lệ khi đủ 3 phần tử, không rỗng, không trùng nhau, không trùng đáp án
    đúng."""
    if len(options) != REQUIRED_COUNT:
        return False

    seen: set[str] = set()
    correct = _normalise(correct_answer)
    for option in options:
        if not option.strip():
            return False
        key = _normalise(option)
        if key == correct or key in seen:
            return False
        seen.add(key)
    return True


def _normalise(value: str | None) -> str:
    return "" if value is None else value.strip().lower()


def _field(payload: Any, name: str) -> Any:
    return payload.get(name) if isinstance(payload, dict) else None


def _read_strings(value: Any) -> list[str]:
    """Phần tử không phải chuỗi thành chuỗi rỗng, để validator loại cả bộ.

    Giữ nguyên hành vi bản Java (`asText(null)` trả null → bộ không hợp lệ): một phần tử
    sai kiểu làm hỏng cả bộ chứ không bị lặng lẽ bỏ qua, vì bỏ qua sẽ để lại một mảng 2 phần
    tử và câu trắc nghiệm thiếu lựa chọn.
    """
    if not isinstance(value, list):
        return []
    return [item if isinstance(item, str) else "" for item in value]


def _render(body: str, variables: dict[str, str]) -> str:
    out = body
    for key, value in variables.items():
        out = out.replace("{{" + key + "}}", value)
    return out


@lru_cache(maxsize=1)
def _load_prompt() -> tuple[str, int]:
    """Đọc prompt từ `prompts/srs-distractors.md`: header `version: N`, một dòng `---`, rồi
    tới nội dung.

    Version đi vào `srs_distractor.prompt_version` nên sửa nội dung prompt PHẢI tăng
    `version:` — đó là cách duy nhất làm mồi nhử cũ hết hiệu lực (ràng buộc #5, cùng nguyên
    tắc với `lookup_cache`).

    Cache bằng `lru_cache` vì file không đổi trong một lần chạy, y như `ConcurrentHashMap`
    bên Java.
    """
    path = API_SERVICE_ROOT / "prompts" / PROMPT_FILE
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as ex:
        raise AppError.of(ErrorCode.INTERNAL, f"Không đọc được prompt: {path}") from ex

    lines = raw.split("\n")
    delimiter = next((i for i, line in enumerate(lines) if line.strip() == "---"), -1)
    if delimiter < 0:
        raise AppError.of(ErrorCode.INTERNAL, f"Prompt thiếu dòng phân cách '---': {path}")

    header = "\n".join(lines[:delimiter]).strip()
    body = "\n".join(lines[delimiter + 1 :]).strip()
    if not header.startswith("version:"):
        raise AppError.of(ErrorCode.INTERNAL, f"Prompt thiếu header 'version:': {path}")
    try:
        version = int(header[len("version:") :].strip())
    except ValueError as ex:
        raise AppError.of(ErrorCode.INTERNAL, f"Prompt có version không phải số: {path}") from ex
    return body, version
