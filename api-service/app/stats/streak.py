"""Tính streak từ danh sách ngày có lượt ôn.

Hàm thuần: không chạm `Session`, không gọi `date.today()` bên trong. Tách khỏi `service.py`
cùng lý do `srs/scheduler.py` tách khỏi `srs/service.py` — logic ngày tháng là chỗ off-by-one
sống lâu nhất, và nó chỉ test được tử tế khi `today` là tham số.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise


@dataclass(frozen=True)
class Streak:
    current: int
    longest: int
    last_active: date | None


def tinh_streak(active_days: list[date], today: date) -> Streak:
    """`active_days` phải đã sắp xếp TĂNG DẦN và không trùng lặp — repository đảm bảo cả hai
    bằng `GROUP BY ngay ORDER BY ngay`.

    Hôm nay chưa ôn thì streak VẪN tính từ hôm qua. Streak chỉ đứt khi cả hôm nay lẫn hôm qua
    đều trống — đúng cách Anki và Duolingo làm.
    """
    if not active_days:
        return Streak(current=0, longest=0, last_active=None)

    co_on = set(active_days)
    longest = _chuoi_dai_nhat(active_days)
    last_active = active_days[-1]

    moc = today if today in co_on else today - timedelta(days=1)
    if moc not in co_on:
        return Streak(current=0, longest=longest, last_active=last_active)

    current = 0
    while moc in co_on:
        current += 1
        moc -= timedelta(days=1)

    return Streak(current=current, longest=longest, last_active=last_active)


def _chuoi_dai_nhat(days: list[date]) -> int:
    """Chuỗi ngày liên tiếp dài nhất trong toàn bộ lịch sử. `days` khác rỗng."""
    dai_nhat = 1
    hien_tai = 1
    for truoc, sau in pairwise(days):
        hien_tai = hien_tai + 1 if sau - truoc == timedelta(days=1) else 1
        dai_nhat = max(dai_nhat, hien_tai)
    return dai_nhat
