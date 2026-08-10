"""Công thức SM-2 rút gọn: chỉ interval theo ngày, không có learning step trong ngày.

Hàm thuần — không đọc DB, không đọc đồng hồ hệ thống (`today` truyền vào). Đây là điều kiện
để test bằng bảng thuần tuý, và là lý do module này không giữ state nào.

ΔEF dùng đúng MỘT công thức cho cả bốn rating:
`0.1 − (3−q)·(0.08 + (3−q)·0.02)` → AGAIN −0.32, HARD −0.14, GOOD 0, EASY +0.10.
Design gốc 2026-08-03 có ghi thêm "EF -= 0.2" ở dòng AGAIN; con số đó mâu thuẫn với chính
công thức bên dưới nó và đã bị loại trong spec Phase 2/3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from app.srs.models import CardState, Rating, SrsCard

MIN_EASE_FACTOR = 1.3
HARD_MULTIPLIER = 1.2
EASY_BONUS = 1.3


@dataclass(frozen=True)
class Schedule:
    """Kết quả tính lịch cho một lượt review. Không chạm DB."""

    interval_days: int
    ease_factor: float
    repetitions: int
    lapses: int
    due_date: date
    state: CardState


def next_schedule(card: SrsCard, rating: Rating, today: date) -> Schedule:
    ease_factor = max(MIN_EASE_FACTOR, card.ease_factor + _ease_delta(rating))
    repetitions = 0 if rating == Rating.AGAIN else card.repetitions + 1
    lapses = card.lapses + 1 if rating == Rating.AGAIN else card.lapses
    state = CardState.RELEARNING if rating == Rating.AGAIN else CardState.REVIEW
    interval_days = _interval_for(rating, card.interval_days, repetitions, ease_factor)

    return Schedule(
        interval_days=interval_days,
        ease_factor=ease_factor,
        repetitions=repetitions,
        lapses=lapses,
        due_date=today + timedelta(days=interval_days),
        state=state,
    )


def _ease_delta(rating: Rating) -> float:
    diff = 3 - rating.q
    return 0.1 - diff * (0.08 + diff * 0.02)


def _interval_for(
    rating: Rating, current_interval: int, repetitions: int, ease_factor: float
) -> int:
    """EF truyền vào đây là EF ĐÃ cập nhật, không phải EF cũ."""
    if rating == Rating.AGAIN:
        return 1
    if rating == Rating.HARD:
        return _at_least_one_day(_round_half_up(current_interval * HARD_MULTIPLIER))

    if repetitions == 1:
        base = 1
    elif repetitions == 2:
        base = 6
    else:
        base = _round_half_up(current_interval * ease_factor)

    if rating == Rating.EASY:
        base = _round_half_up(base * EASY_BONUS)
    return _at_least_one_day(base)


def _round_half_up(value: float) -> int:
    """Làm tròn NỬA LÊN, đúng như `Math.round` của Java (`floor(x + 0.5)`).

    KHÔNG dùng `round()` của Python: nó làm tròn về số chẵn (round-half-even), nên
    `round(16.5)` ra 16 trong khi Java ra 17. Sai một ngày ở đây không làm gì đỏ cả — lịch
    ôn của người dùng chỉ lệch dần so với bản Java mà không ai thấy.
    """
    return math.floor(value + 0.5)


def _at_least_one_day(value: int) -> int:
    return max(1, value)
