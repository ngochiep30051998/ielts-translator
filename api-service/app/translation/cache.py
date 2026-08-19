"""Khoá cache của một lượt tra — bản port của `TranslationService.cacheKey/appendField`.

Đây là chỗ dễ port sai nhất và cũng là chỗ port sai không gây ra lỗi nào: khoá lệch một ký
tự thì toàn bộ `lookup_cache` hiện có trở thành rác, không exception, không log, chỉ là mọi
lượt tra đều gọi lại Gemini và hoá đơn quota tăng gấp đôi trong im lặng.

Khoá gồm sáu thành phần: text + context + direction + mode + model + prompt version.
"""

from __future__ import annotations

import hashlib

from app.translation.models import Direction, Mode


def utf16_length(value: str) -> int:
    """Độ dài theo ĐƠN VỊ MÃ UTF-16 — đúng thứ `String.length()` bên Java trả về.

    `len()` của Python đếm code point, Java đếm code unit UTF-16: một emoji là 1 với Python
    và 2 với Java. Con số này là tiền tố độ dài trong material băm, nên lệch là ra khoá
    khác cho cùng một đoạn text. Không dùng `len(value.encode("utf-16-le")) // 2` vì chuỗi
    chứa lone surrogate (JSON có thể sinh ra) sẽ làm `encode` ném lỗi.
    """
    return len(value) + sum(1 for char in value if ord(char) > 0xFFFF)


def java_trim(value: str) -> str:
    """Bản sao của `String.trim()` bên Java: chỉ cắt ký tự có mã <= U+0020.

    KHÔNG dùng `str.strip()` của Python — nó cắt cả khoảng trắng Unicode, trong đó U+00A0
    (`&nbsp;`) nhan nhản ở text bôi đen từ web. Cắt nhiều hơn bản Java một ký tự là sinh ra
    một khoá cache khác cho cùng một đoạn text.
    """
    start = 0
    end = len(value)
    while start < end and value[start] <= " ":
        start += 1
    while end > start and value[end - 1] <= " ":
        end -= 1
    return value[start:end]


def _append_field(parts: list[str], value: str | None) -> None:
    """Nối một field vào material dạng "độDài:nộiDung|" thay vì nối chuỗi trực tiếp có/không
    dấu phân cách. Text và context là văn bản người dùng bôi đen tuỳ ý trên web, có thể
    chứa bất kỳ ký tự nào (kể cả ký tự điều khiển do lỗi encoding khi paste) nên không thể
    dựa vào giả định "ký tự phân cách này không bao giờ xuất hiện trong dữ liệu người dùng".
    Tiền tố độ dài đảm bảo hai bộ input khác nhau — ví dụ ("ab","c") và ("a","bc") — không
    bao giờ sinh ra cùng một chuỗi material, bất kể nội dung field chứa gì.
    """
    safe = "" if value is None else value
    parts.append(f"{utf16_length(safe)}:{safe}|")


def build_cache_key(
    *,
    text: str,
    context: str | None,
    direction: Direction,
    mode: Mode,
    model: str,
    prompt_version: int,
) -> str:
    """SHA-256 hex (chữ thường) của material, y hệt bản Java.

    Tham số CHỈ nhận theo tên: sáu thành phần đều là chuỗi/số nên gọi nhầm thứ tự vẫn chạy
    ngon, chỉ là mọi khoá sinh ra đều khác bản Java. Bắt gọi theo tên là cách rẻ nhất để
    biến lớp lỗi im lặng đó thành lỗi lúc gọi.

    `context` đi vào khoá để hai lượt tra cùng text nhưng khác ngữ cảnh không đụng độ nhau.
    `prompt_version` đi vào khoá vì đó là cách DUY NHẤT làm cache cũ hết hiệu lực khi sửa
    nội dung prompt (ràng buộc #5).
    """
    parts: list[str] = []
    _append_field(parts, text)
    _append_field(parts, context)
    _append_field(parts, direction.value)
    _append_field(parts, mode.value)
    _append_field(parts, model)
    _append_field(parts, str(prompt_version))
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()
