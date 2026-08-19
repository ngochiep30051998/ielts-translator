"""Bản port của `TranslationSchemasTest`.

Bốn tổ hợp direction × mode sinh ra **bốn hình dạng payload khác nhau**. File này ghim tên
từng field lại. Nghe như test tautology — cho tới khi nhớ rằng những tên này đi thẳng vào
`responseSchema` gửi cho Gemini, rồi từ payload Gemini trả về đi thẳng ra bubble qua
`extension/src/shared/types.ts` (ràng buộc #3). Đổi `meaning_vi` thành `meaningVi` ở đây
không làm gì đỏ ở phía backend cả: model vẫn trả JSON hợp lệ, cache vẫn ghi, chỉ là bubble
hiện trống.
"""

from __future__ import annotations

from typing import Any

from app.translation.models import Direction, Mode
from app.translation.schemas import schema_for


def _required(d: Direction, m: Mode) -> list[str]:
    required = schema_for(d, m)["required"]
    assert isinstance(required, list)
    return required


def _nested_item(d: Direction, m: Mode, array_property: str) -> dict[str, Any]:
    """Schema của phần tử bên trong một property kiểu mảng."""
    items = schema_for(d, m)["properties"][array_property]["items"]
    assert isinstance(items, dict)
    return items


def _keys(schema_object: dict[str, Any]) -> set[str]:
    return set(schema_object["properties"].keys())


# ── required của bốn tuyến ────────────────────────────────────────────────────


def test_en_vi_word_requires_all_bubble_fields_and_detail_fields() -> None:
    """Bubble hiển thị `meaning_vi`/`ipa`/`pos`; panel chi tiết dùng phần còn lại.

    Thiếu một field trong `required` là mở đường cho model bỏ qua nó — và chỗ đó trên UI
    trống mà không có lỗi nào.
    """
    assert set(_required(Direction.EN_VI, Mode.WORD)) >= {
        "term",
        "ipa",
        "pos",
        "meaning_vi",
        "definition_en",
        "cefr",
        "band_level",
        "register",
        "collocations",
        "examples",
        "synonyms",
    }


def test_en_vi_sentence_requires_the_translation_and_key_vocab() -> None:
    assert set(_required(Direction.EN_VI, Mode.SENTENCE)) >= {
        "translation_vi",
        "key_vocab",
        "structure_note",
    }


def test_vi_en_word_requires_best_en_and_alternatives() -> None:
    assert set(_required(Direction.VI_EN, Mode.WORD)) >= {
        "best_en",
        "alternatives",
        "collocations",
        "examples",
    }


def test_vi_en_sentence_requires_the_band_version_and_the_explanation() -> None:
    assert set(_required(Direction.VI_EN, Mode.SENTENCE)) >= {
        "band65_version",
        "why_notes",
        "key_phrases",
        "avoid",
    }


# ── tên field lồng nhau ───────────────────────────────────────────────────────


def test_en_vi_word_nested_field_names_are_pinned() -> None:
    """`containsExactlyInAnyOrder` bên Java: thừa field cũng là sai.

    Một field lạ trong schema là một field bubble không biết đọc, và là token model phải
    sinh ra vô ích ở mọi lượt tra.
    """
    assert _keys(_nested_item(Direction.EN_VI, Mode.WORD, "examples")) == {"en", "vi"}
    assert _keys(_nested_item(Direction.EN_VI, Mode.WORD, "synonyms")) == {"term", "band"}


def test_en_vi_sentence_nested_field_names_are_pinned() -> None:
    assert _keys(_nested_item(Direction.EN_VI, Mode.SENTENCE, "key_vocab")) == {
        "term",
        "meaning_vi",
        "band_level",
    }


def test_vi_en_word_nested_field_names_are_pinned() -> None:
    assert _keys(_nested_item(Direction.VI_EN, Mode.WORD, "alternatives")) == {
        "term",
        "band",
        "register",
        "when_to_use",
    }


def test_vi_en_sentence_nested_field_names_are_pinned() -> None:
    assert _keys(_nested_item(Direction.VI_EN, Mode.SENTENCE, "avoid")) == {"phrase", "reason"}


# ── bất biến chung của cả bốn ─────────────────────────────────────────────────


def test_every_schema_is_an_object_with_properties() -> None:
    """Gemini từ chối `responseSchema` không phải object ở gốc — và từ chối lúc chạy thật,
    không phải lúc build."""
    for d in Direction:
        for m in Mode:
            schema = schema_for(d, m)
            assert schema["type"] == "object", f"{d}/{m}"
            assert isinstance(schema["properties"], dict), f"{d}/{m}"


def test_four_combinations_produce_four_different_schemas() -> None:
    """Phần bù cho việc Python không có `switch` exhaustive.

    Bên Java, `of()` rẽ bằng hai câu điều kiện lồng nhau và trình biên dịch không giúp gì;
    bên Python thì `match` + `assert_never` mới bắt được lúc mypy chạy. Cách rẻ nhất để phát
    hiện một nhánh trỏ nhầm hàm (ví dụ VI_EN/SENTENCE trả về schema của VI_EN/WORD) là
    khẳng định bốn kết quả đôi một khác nhau — đúng cái mà "bốn hình dạng payload" nghĩa là.
    """
    all_combos = [(d, m, schema_for(d, m)) for d in Direction for m in Mode]
    for i, (d1, m1, s1) in enumerate(all_combos):
        for d2, m2, s2 in all_combos[i + 1 :]:
            assert s1 != s2, f"{d1}/{m1} và {d2}/{m2} ra cùng một schema"


def test_each_call_returns_a_new_dict() -> None:
    """Bên Java `Map.of(...)` bất biến nên không ai sửa được schema tại chỗ; dict của Python
    thì sửa được thoải mái. Nếu `schema_for` trả về cùng một object dùng chung, một chỗ nào
    đó lỡ tay `schema["required"].append(...)` sẽ làm hỏng schema của MỌI lượt tra sau đó —
    chỉ trong tiến trình đang chạy, nên không bao giờ tái hiện được ở máy dev.
    """
    first = schema_for(Direction.EN_VI, Mode.WORD)
    first["properties"]["term"]["type"] = "number"
    first["required"].append("bia-dat")

    second = schema_for(Direction.EN_VI, Mode.WORD)
    assert second["properties"]["term"] == {"type": "string"}
    assert "bia-dat" not in second["required"]
