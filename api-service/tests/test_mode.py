"""Bản port của `ModeTest`.

Ngưỡng ≤3 token quyết định dùng prompt `-word` hay `-sentence`, và nó cũng nằm trong khoá
cache — phân loại sai là dịch bằng prompt sai VÀ ghi cache dưới khoá sai cùng lúc.
"""

from __future__ import annotations

import pytest

from app.translation.models import Direction, Mode

NBSP = " "


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("renewable", Mode.WORD),
        ("climate change", Mode.WORD),
        ("renewable energy sources", Mode.WORD),
        # Khoảng trắng thừa không được tính thành token — tách rồi mới đếm.
        ("  renewable   energy   sources  ", Mode.WORD),
        ("the government should allocate funding", Mode.SENTENCE),
        ("năng lượng tái tạo là xu hướng", Mode.SENTENCE),
    ],
)
def test_mode_classification(text: str, expected: Mode) -> None:
    assert Mode.of(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "\t\n", None])
def test_empty_string_is_treated_as_word(text: str | None) -> None:
    """Không được nổ lỗi: `Mode.of` nằm trên đường nóng của mọi lượt dịch."""
    assert Mode.of(text) is Mode.WORD


def test_exactly_three_tokens_still_word_four_tokens_becomes_sentence() -> None:
    """Chốt đúng cái ngưỡng, không phải chốt quanh nó."""
    assert Mode.of("a b c") is Mode.WORD
    assert Mode.of("a b c d") is Mode.SENTENCE


def test_unicode_whitespace_is_not_counted_as_token_separator() -> None:
    r"""Lệch chỉ tồn tại ở bản Python.

    `\s` của Java là `[ \t\n\x0B\f\r]` — thuần ASCII. `\s` của Python bao cả khoảng trắng
    Unicode, trong đó có U+00A0 (`&nbsp;`) vốn nhan nhản trong text bôi đen từ web. Dùng
    `\s` ở đây thì một cụm bốn chữ nối bằng `&nbsp;` ra WORD ở bản Java và SENTENCE ở bản
    này: hai hình dạng payload khác nhau cho cùng một chuỗi, và hai khoá cache khác nhau.
    """
    assert Mode.of(NBSP.join(["a", "b", "c", "d"])) is Mode.WORD
    assert Mode.of("a b c d") is Mode.SENTENCE


def test_enum_constant_names_go_straight_into_json() -> None:
    """`Mode` và `Direction` xuất hiện nguyên tên trong response `/api/translate`, và
    `shared/types.ts` phân nhánh theo chúng."""
    assert {m.value for m in Mode} == {"WORD", "SENTENCE"}
    assert {d.value for d in Direction} == {"EN_VI", "VI_EN"}
