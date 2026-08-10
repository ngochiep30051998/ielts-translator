"""Xuất sổ từ ra CSV — bản port của `CsvExporter`.

Đây là đường thoát dữ liệu duy nhất của người dùng: nếu một ngày họ bỏ công cụ này, file
CSV là thứ họ mang đi. Nên header, thứ tự cột, cách escape và cách nối tag phải giữ y hệt
bản Java — một file đã export hôm qua và một file export hôm nay phải nhập được vào cùng
một chỗ (Anki, Excel, Google Sheets).

Cố ý KHÔNG dùng `csv` của thư viện chuẩn: `csv.writer` mặc định kết thúc dòng bằng `\\r\\n`
và quyết định escape theo luật riêng của nó. Bản Java nối tay bằng `\\n` và chỉ bọc ngoặc
kép khi thật sự cần — chép đúng luật đó rẻ hơn là ép `csv` cư xử giống nó.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from app.vocabulary.models import VocabEntry

HEADER = "term,pos,ipa,meaning_vi,definition_en,cefr,band_level,tags,source_url,created_at"


def to_csv(entries: Iterable[VocabEntry]) -> str:
    rows = [HEADER]
    for e in entries:
        rows.append(
            ",".join(
                (
                    _escape(e.term),
                    _escape(e.pos),
                    _escape(e.ipa),
                    _escape(e.meaning_vi),
                    _escape(e.definition_en),
                    _escape(e.cefr),
                    _escape(e.band_level),
                    _escape(";".join(e.tags or ())),
                    _escape(e.source_url),
                    _escape(_format_instant(e.created_at)),
                )
            )
        )
    return "\n".join(rows)


def _escape(value: str | None) -> str:
    """Bọc dấu ngoặc kép khi field chứa dấu phẩy, ngoặc kép hoặc xuống dòng (RFC 4180)."""
    if value is None:
        return ""
    if "," in value or '"' in value or "\n" in value or "\r" in value:
        return '"' + value.replace('"', '""') + '"'
    return value


def _format_instant(value: datetime | None) -> str:
    """Định dạng mốc thời gian đúng như `Instant.toString()` của Java.

    Java in 0, 3, 6 hoặc 9 chữ số phần lẻ giây (bỏ nhóm số 0 cuối), còn `isoformat()` của
    Python luôn in 0 hoặc 6 và dùng hậu tố `+00:00` thay cho `Z`. Không san hai khác biệt
    này thì cùng một hàng dữ liệu xuất ra hai chuỗi khác nhau tuỳ backend nào đang chạy —
    đúng thứ làm hỏng một script nhập liệu của người dùng mà không ai báo lỗi.
    """
    if value is None:
        return ""
    # Cột là TIMESTAMPTZ nên giá trị luôn có tzinfo; nhánh naive chỉ để test dựng entity
    # trong bộ nhớ không phải bận tâm — Instant của Java vốn cũng luôn là UTC.
    utc = value.astimezone(UTC) if value.tzinfo is not None else value
    micros = utc.microsecond
    base = utc.strftime("%Y-%m-%dT%H:%M:%S")
    if micros == 0:
        return base + "Z"
    if micros % 1000 == 0:
        return f"{base}.{micros // 1000:03d}Z"
    return f"{base}.{micros:06d}Z"
