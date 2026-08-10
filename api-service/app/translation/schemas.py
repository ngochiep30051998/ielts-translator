"""Response schema gửi cho Gemini (tập con OpenAPI mà Gemini chấp nhận).

Bốn tổ hợp direction × mode sinh ra BỐN hình dạng payload khác nhau. Đây là nơi định nghĩa
hợp đồng đó ở phía backend; `extension/src/shared/types.ts` là bản gương phía extension và
mọi UI hiển thị kết quả phải phân nhánh theo `direction` + `mode`.
"""

from __future__ import annotations

from typing import Any, assert_never

from app.translation.models import Direction, Mode

_BANDS = ["5.5", "6.0", "6.5", "7.0", "7.5", "8.0"]
_CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"]
_REGISTERS = ["academic", "neutral", "informal"]


def schema_for(direction: Direction, mode: Mode) -> dict[str, Any]:
    match direction:
        case Direction.EN_VI:
            return _en_vi(mode)
        case Direction.VI_EN:
            return _vi_en(mode)
    assert_never(direction)


def _en_vi(mode: Mode) -> dict[str, Any]:
    match mode:
        case Mode.WORD:
            return _en_vi_word()
        case Mode.SENTENCE:
            return _en_vi_sentence()
    assert_never(mode)


def _vi_en(mode: Mode) -> dict[str, Any]:
    match mode:
        case Mode.WORD:
            return _vi_en_word()
        case Mode.SENTENCE:
            return _vi_en_sentence()
    assert_never(mode)


def _en_vi_word() -> dict[str, Any]:
    return _object(
        {
            "term": _str(),
            "lemma": _str(),
            "pos": _str(),
            "ipa": _str(),
            "meaning_vi": _str(),
            "definition_en": _str(),
            "cefr": _enum_of(_CEFR),
            "band_level": _enum_of(_BANDS),
            "register": _enum_of(_REGISTERS),
            "collocations": _array_of(_str()),
            "examples": _array_of(_object({"en": _str(), "vi": _str()}, ["en", "vi"])),
            "synonyms": _array_of(
                _object({"term": _str(), "band": _enum_of(_BANDS)}, ["term", "band"])
            ),
        },
        [
            "term",
            "lemma",
            "pos",
            "ipa",
            "meaning_vi",
            "definition_en",
            "cefr",
            "band_level",
            "register",
            "collocations",
            "examples",
            "synonyms",
        ],
    )


def _en_vi_sentence() -> dict[str, Any]:
    return _object(
        {
            "translation_vi": _str(),
            "key_vocab": _array_of(
                _object(
                    {"term": _str(), "meaning_vi": _str(), "band_level": _enum_of(_BANDS)},
                    ["term", "meaning_vi", "band_level"],
                )
            ),
            "structure_note": _str(),
        },
        ["translation_vi", "key_vocab", "structure_note"],
    )


def _vi_en_word() -> dict[str, Any]:
    return _object(
        {
            "best_en": _str(),
            "alternatives": _array_of(
                _object(
                    {
                        "term": _str(),
                        "band": _enum_of(_BANDS),
                        "register": _enum_of(_REGISTERS),
                        "when_to_use": _str(),
                    },
                    ["term", "band", "register", "when_to_use"],
                )
            ),
            "collocations": _array_of(_str()),
            "examples": _array_of(_str()),
        },
        ["best_en", "alternatives", "collocations", "examples"],
    )


def _vi_en_sentence() -> dict[str, Any]:
    return _object(
        {
            "band65_version": _str(),
            "why_notes": _array_of(_str()),
            "key_phrases": _array_of(_str()),
            "avoid": _array_of(_object({"phrase": _str(), "reason": _str()}, ["phrase", "reason"])),
        },
        ["band65_version", "why_notes", "key_phrases", "avoid"],
    )


# --- helper dựng schema ---
# Mỗi helper trả về dict MỚI. Dùng chung một dict hằng sẽ tiết kiệm được vài byte và mở ra
# khả năng một chỗ nào đó sửa tại chỗ làm hỏng schema của mọi lượt tra sau đó.


def _str() -> dict[str, Any]:
    return {"type": "string"}


def _enum_of(values: list[str]) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


def _array_of(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


def _object(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(required)}
