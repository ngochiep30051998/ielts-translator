"""Kiểm tra từng item Gemini trả về. Hàm thuần — không DB, không mạng.

Khác bộ kiểm mồi nhử của srs một cách CÓ CHỦ Ý: ở đây loại TỪNG item hỏng rồi lấy tiếp phần
còn lại, không giết cả lô. Một lô 10 câu mà hỏng 1 câu thì 9 câu kia vẫn dùng được, và người
dùng đang đứng chờ — bắt họ đợi thêm một lượt gọi Gemini nữa chỉ vì một câu hỏng là đắt vô
lý. Bên mồi nhử thì ngược lại: việc chạy nền, không ai chờ.
"""

from __future__ import annotations

from collections.abc import Sequence

#: Chỗ trống trong câu điền từ. Đúng ba gạch dưới, khớp với prompt.
BLANK = "___"

_REQUIRED_OPTIONS = 4


def is_valid_fill_blank(sentence: str | None, answer: str | None, hint: str | None) -> bool:
    """Hợp lệ khi: câu chứa `___`, đáp án không rỗng, đáp án KHÔNG xuất hiện nguyên văn ở
    phần còn lại của câu, và gợi ý khác rỗng mà cũng không chứa đáp án (bỏ phân biệt hoa
    thường ở cả hai phép so).

    Vì sao hint cũng bị soi: `question` của FILL_BLANK được dựng thành "Điền từ còn thiếu vào
    chỗ trống. Gợi ý: " + hint, nên hint rỗng cho ra một đề cụt, còn hint chứa đáp án thì lộ
    đáp án ngay trên đề — đúng thứ mà DTO đang cố giấu.
    """
    if sentence is None or answer is None or not answer.strip():
        return False
    if hint is None or not hint.strip():
        return False
    if BLANK not in sentence:
        return False
    needle = answer.strip().lower()
    khong_con_cho_trong = sentence.replace(BLANK, " ").lower()
    if needle in khong_con_cho_trong:
        return False
    return needle not in hint.lower()


def is_valid_collocation(options: Sequence[str | None] | None, correct_index: int | None) -> bool:
    """Hợp lệ khi: đúng 4 lựa chọn, không rỗng, không trùng nhau, index trong 0..3."""
    if options is None or correct_index is None or len(options) != _REQUIRED_OPTIONS:
        return False
    if correct_index < 0 or correct_index >= _REQUIRED_OPTIONS:
        return False
    da_thay: set[str] = set()
    for option in options:
        if option is None or not option.strip():
            return False
        chuan = option.strip().lower()
        if chuan in da_thay:
            return False
        da_thay.add(chuan)
    return True
