"""Bản port của `DistractorValidatorTest` — hàm thuần, không DB, không mạng.

Nguyên tắc của validator: **loại CẢ bộ khi có bất kỳ vi phạm nào**, thay vì cố vá từng
phần tử. Bộ đã hỏng thì phần còn lại cũng không đáng tin, và để lần sau sinh lại rẻ hơn
nhiều so với việc người học gặp một câu hỏi có hai đáp án cùng đúng.

Mỗi luật một test — đó là cách duy nhất để khi một luật bị gỡ thì biết được luật NÀO.
"""

from __future__ import annotations

from typing import Any

from app.srs import distractors
from app.srs.distractors import is_valid
from app.srs.models import DistractorSet

MEANING = "giảm nhẹ"
TERM = "mitigate"


def _distractor_set(vi: list[str], en: list[str]) -> DistractorSet:
    return DistractorSet(vi_options=vi, en_options=en)


def _valid_distractor_set() -> DistractorSet:
    return _distractor_set(
        ["làm trầm trọng thêm", "phóng đại", "trì hoãn"],
        ["aggravate", "exaggerate", "postpone"],
    )


def _distractor_set_from_payload(payload: Any) -> DistractorSet:
    """Dựng bộ mồi nhử ĐÚNG như `_generate_for` dựng nó từ JSON Gemini trả về.

    Bên Java, `readStrings` chạy trên `JsonNode` nên null lọt được vào `List<String>` và
    validator phải tự chống NPE. Ở Python `DistractorSet` là model pydantic với
    `list[str]`, nên null không bao giờ đi thẳng vào được — nó bị chặn sớm hơn một bước, ở
    `_field` + `_read_strings`. Muốn kiểm cùng lớp lỗi thì phải đi qua đúng hai hàm đó,
    chứ không phải nhồi `None` vào một chỗ mà code thật không thể nhồi.
    """
    return DistractorSet(
        vi_options=distractors._read_strings(distractors._field(payload, "vi_options")),
        en_options=distractors._read_strings(distractors._field(payload, "en_options")),
    )


def test_set_with_three_options_per_direction_no_duplicates_no_correct_answer_is_valid() -> None:
    """Ca nền: bộ sạch phải được nhận. Không có test này thì một validator luôn trả False
    vẫn làm mọi test còn lại xanh."""
    assert is_valid(_valid_distractor_set(), MEANING, TERM) is True


def test_too_few_options_is_rejected() -> None:
    """Hai mồi nhử = câu trắc nghiệm chỉ có ba lựa chọn, xác suất đoán bừa nhảy từ 25% lên
    33%."""
    assert (
        is_valid(
            _distractor_set(
                ["làm trầm trọng thêm", "phóng đại"], ["aggravate", "exaggerate", "postpone"]
            ),
            MEANING,
            TERM,
        )
        is False
    )


def test_too_many_options_is_rejected() -> None:
    """Gemini trả 4 nghĩa là dấu hiệu nó hiểu sai đề — không cắt bớt lấy 3, vì bộ sinh ra từ
    một lần hiểu sai thì phần tử nào cũng đáng ngờ."""
    assert (
        is_valid(
            _distractor_set(["a", "b", "c"], ["aggravate", "exaggerate", "postpone", "delay"]),
            MEANING,
            TERM,
        )
        is False
    )


def test_empty_or_whitespace_only_option_is_rejected() -> None:
    """Một lựa chọn trống hiện ra màn hình là một ô rỗng người học không bấm được."""
    assert (
        is_valid(
            _distractor_set(
                ["làm trầm trọng thêm", "   ", "trì hoãn"],
                ["aggravate", "exaggerate", "postpone"],
            ),
            MEANING,
            TERM,
        )
        is False
    )


def test_two_duplicate_options_in_same_direction_is_rejected() -> None:
    """So sau khi chuẩn hoá (strip + lowercase): "phóng đại" và "Phóng Đại" là MỘT lựa chọn
    hiện hai lần, dù chuỗi khác nhau."""
    assert (
        is_valid(
            _distractor_set(
                ["phóng đại", "Phóng Đại", "trì hoãn"], ["aggravate", "exaggerate", "postpone"]
            ),
            MEANING,
            TERM,
        )
        is False
    )


def test_distractor_matching_the_correct_meaning_is_rejected() -> None:
    """Hai lựa chọn cùng đúng là giết bài ôn: người học chọn đúng vẫn bị chấm sai.

    Đây là lý do tồn tại của cả validator, và cũng là ca so sánh phải chuẩn hoá — Gemini
    hay trả lại đáp án đúng dưới dạng khác hoa thường hoặc thừa khoảng trắng.
    """
    assert (
        is_valid(
            _distractor_set(
                ["  Giảm Nhẹ ", "phóng đại", "trì hoãn"], ["aggravate", "exaggerate", "postpone"]
            ),
            MEANING,
            TERM,
        )
        is False
    )


def test_distractor_matching_the_term_being_asked_is_rejected() -> None:
    """Chiều EN cũng phải được kiểm, không chỉ chiều VI: câu hỏi "từ nào có nghĩa giảm nhẹ"
    mà trong bốn lựa chọn có sẵn `mitigate` hai lần là hỏng y hệt."""
    assert (
        is_valid(
            _distractor_set(
                ["làm trầm trọng thêm", "phóng đại", "trì hoãn"],
                ["MITIGATE", "exaggerate", "postpone"],
            ),
            MEANING,
            TERM,
        )
        is False
    )


def test_missing_field_or_non_array_field_is_rejected_without_raising() -> None:
    """Tương ứng `isValid(null, ...)` và `set(null, [...])` bên Java.

    Payload Gemini là dữ liệu ngoài tầm kiểm soát: thiếu hẳn field, hoặc field là chuỗi/số
    thay vì mảng. Cả hai phải cho ra "bộ không hợp lệ", KHÔNG được ném lỗi — vì lỗi ném ra
    ở đây chạy trong tác vụ nền, chỗ không ai đọc traceback.
    """
    assert is_valid(_distractor_set_from_payload({}), MEANING, TERM) is False
    assert (
        is_valid(_distractor_set_from_payload({"en_options": ["a", "b", "c"]}), MEANING, TERM)
        is False
    )
    assert (
        is_valid(
            _distractor_set_from_payload(
                {"vi_options": "không phải mảng", "en_options": ["a", "b", "c"]}
            ),
            MEANING,
            TERM,
        )
        is False
    )
    assert (
        is_valid(_distractor_set_from_payload("cả payload không phải object"), MEANING, TERM)
        is False
    )


def test_non_string_option_invalidates_whole_set_without_raising() -> None:
    """Tương ứng `Arrays.asList("a", null, "c")` bên Java.

    Phần tử sai kiểu bị biến thành chuỗi rỗng để validator loại CẢ bộ, chứ không bị lặng lẽ
    bỏ qua — bỏ qua sẽ để lại một mảng 2 phần tử và câu trắc nghiệm thiếu lựa chọn.
    """
    assert (
        is_valid(
            _distractor_set_from_payload(
                {"vi_options": ["a", None, "c"], "en_options": ["x", "y", "z"]}
            ),
            MEANING,
            TERM,
        )
        is False
    )
    assert (
        is_valid(
            _distractor_set_from_payload(
                {"vi_options": ["a", "b", "c"], "en_options": ["x", 7, "z"]}
            ),
            MEANING,
            TERM,
        )
        is False
    )


def test_correct_answer_none_does_not_raise_and_set_still_valid() -> None:
    """`_normalise(None)` trả chuỗi rỗng, đúng như `normalise(null)` bên Java.

    Không có nhánh này thì một từ thiếu `definition_en`/`meaning_vi` (dữ liệu cũ, hoặc từ
    nhập tay) sẽ làm tác vụ nền ném `AttributeError` thay vì sinh mồi nhử. Chuỗi rỗng cũng
    không bao giờ khớp một mồi nhử hợp lệ, vì mồi nhử rỗng đã bị luật "không rỗng" loại
    trước rồi.
    """
    assert is_valid(_valid_distractor_set(), None, None) is True
