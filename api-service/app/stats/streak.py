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


def compute_streak(active_days: list[date], today: date) -> Streak:
    """`active_days` phải đã sắp xếp TĂNG DẦN và không trùng lặp — repository đảm bảo cả hai
    bằng `GROUP BY day ORDER BY day`.

    Hôm nay chưa ôn thì streak VẪN tính từ hôm qua. Streak chỉ đứt khi cả hôm nay lẫn hôm qua
    đều trống — đúng cách Anki và Duolingo làm.
    """
    if not active_days:
        return Streak(current=0, longest=0, last_active=None)

    active_day_set = set(active_days)
    longest = _longest_streak(active_days)
    last_active = active_days[-1]

    cursor = today if today in active_day_set else today - timedelta(days=1)
    if cursor not in active_day_set:
        return Streak(current=0, longest=longest, last_active=last_active)

    current = 0
    while cursor in active_day_set:
        current += 1
        cursor -= timedelta(days=1)

    return Streak(current=current, longest=longest, last_active=last_active)


def _longest_streak(days: list[date]) -> int:
    """Chuỗi ngày liên tiếp dài nhất trong toàn bộ lịch sử. `days` khác rỗng."""
    longest_run = 1
    current_run = 1
    for prev_day, curr_day in pairwise(days):
        current_run = current_run + 1 if curr_day - prev_day == timedelta(days=1) else 1
        longest_run = max(longest_run, current_run)
    return longest_run
