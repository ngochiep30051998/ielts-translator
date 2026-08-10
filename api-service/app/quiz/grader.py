"""Chấm hai loại quiz chấm được tại chỗ. Hàm thuần — không DB, không mạng, không Gemini.

FREE_WRITE không nằm ở đây vì nó cần Gemini; đường chấm đó ở `service.py`, cạnh chỗ trừ hạn
mức.
"""

from __future__ import annotations


def grade_fill_blank(user_answer: str | None, expected: str | None) -> bool:
    """So với đúng dạng từ đã bị che. CỐ Ý không lemmatize: đề che dạng "mitigated" thì người
    học phải viết "mitigated". Chấp nhận "mitigate" là dạy sai — chia động từ đúng chính là
    thứ đang luyện.

    Dùng `lower()` chứ không `casefold()`: `casefold` gấp "ß" thành "ss" và vài cặp khác, tức
    nó nhận đúng những cặp mà `equalsIgnoreCase` của bản Java coi là khác nhau. Chỗ này đang
    chấm bài, nới lỏng âm thầm là chấm sai.
    """
    if user_answer is None or expected is None:
        return False
    given = user_answer.strip()
    return bool(given) and given.lower() == expected.strip().lower()


def grade_collocation(user_answer: str | None, correct_index: int) -> bool:
    """Answer đi trên đường truyền LUÔN là string (một hình dạng, không union). Chuỗi không
    parse được thành index tính là SAI, không phải lỗi — người dùng gõ bậy không phải sự cố hệ
    thống, và ném ở đây sẽ biến nó thành HTTP 500.
    """
    if user_answer is None:
        return False
    try:
        return int(user_answer.strip()) == correct_index
    except ValueError:
        return False
