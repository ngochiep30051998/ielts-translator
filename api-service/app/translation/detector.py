"""Đoán chiều dịch của một đoạn text — bản port của `LanguageDetector`.

Hai tầng, cố ý theo thứ tự này: dấu tiếng Việt là bằng chứng chắc chắn nên xét trước; chỉ
khi không có dấu nào mới phải đoán bằng stopword, vì đó là đường của người gõ không dấu.
"""

from __future__ import annotations

import re

from app.translation.models import Direction

#: Ký tự chỉ xuất hiện trong tiếng Việt — thấy một cái là chắc chắn tiếng Việt.
_VI_CHARS = re.compile(
    "[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
    re.IGNORECASE,
)

# fmt: off
# Giữ nguyên cách xuống dòng 10 từ/dòng của bản Java để `diff` hai bên còn đọc được bằng
# mắt. Nội dung hai danh sách này là hợp đồng ngầm giữa hai backend: thêm/bớt một từ là đổi
# kết quả đoán chiều dịch, tức là đổi cả khoá cache của mọi chuỗi không dấu.

#: Stopword tiếng Việt dạng KHÔNG dấu — dùng khi người dùng gõ không dấu.
_VI_STOPWORDS = frozenset(
    {
        "cua", "va", "la", "khong", "cho", "nhung", "duoc", "co", "nay", "voi",
        "tren", "trong", "mot", "cac", "nguoi", "den", "tu", "ra", "khi", "nhu",
        "se", "da", "cung", "phai", "the", "nao", "gi", "ai", "toi", "ban",
        "chung", "minh", "can", "lam", "viec", "tot", "cai",
    }
)

_EN_STOPWORDS = frozenset(
    {
        "the", "and", "is", "of", "to", "in", "that", "it", "for", "on",
        "with", "as", "this", "are", "was", "be", "have", "has", "not", "but",
        "they", "from", "which", "you", "we", "should", "a", "an",
    }
)
# fmt: on

#: Tách token bằng "mọi thứ không phải a-z". Cắt luôn cả dấu câu lẫn chữ số, và vì đã hạ
#: chữ thường trước đó nên chữ hoa không lọt ra ngoài.
_NON_LETTERS = re.compile("[^a-z]+")


def detect(text: str | None) -> Direction:
    """EN_VI khi không xác định được — mặc định này là chủ ý: người dùng chính bôi đen
    tiếng Anh, nên đoán sai về phía EN_VI ít gây khó chịu hơn."""
    if text is None or not text.strip():
        return Direction.EN_VI
    if _VI_CHARS.search(text):
        return Direction.VI_EN

    tokens = _NON_LETTERS.split(text.lower())
    vi_hits = sum(1 for token in tokens if token in _VI_STOPWORDS)
    en_hits = sum(1 for token in tokens if token in _EN_STOPWORDS)
    # Hoà thì về EN_VI, đúng như bản Java (`>` chứ không phải `>=`).
    return Direction.VI_EN if vi_hits > en_hits else Direction.EN_VI


class LanguageDetector:
    """Giữ lại hình dạng object của bản Java cho chỗ nào cần tiêm một detector khác trong
    test. Đường chạy thật gọi thẳng `detect`."""

    def detect(self, text: str | None) -> Direction:
        return detect(text)
