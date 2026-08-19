"""Bản port của `SrsSchedulerTest`, cộng hai ca bản Java không có (xem cuối file).

Hàm thuần, không chạm DB — chạy trong mili giây.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.srs.models import CardState, Rating, SrsCard
from app.srs.scheduler import _round_half_up, next_schedule

TODAY = date(2026, 8, 6)


def make_card(
    ease: float, interval: int, repetitions: int, lapses: int, state: CardState
) -> SrsCard:
    card = SrsCard()
    card.ease_factor = ease
    card.interval_days = interval
    card.repetitions = repetitions
    card.lapses = lapses
    card.state = state.value
    return card


@pytest.mark.parametrize(
    ("rating", "expected_ease"),
    [
        (Rating.AGAIN, 2.18),
        (Rating.HARD, 2.36),
        (Rating.GOOD, 2.50),
        (Rating.EASY, 2.60),
    ],
)
def test_delta_ease_factor_correct_for_each_rating(rating: Rating, expected_ease: float) -> None:
    """ΔEF = 0.1 − (3−q)·(0.08 + (3−q)·0.02).

    Đây là bảng số chốt trong spec — AGAIN là −0.32, KHÔNG phải −0.20 như design gốc
    2026-08-03 viết nhầm.
    """
    result = next_schedule(make_card(2.5, 10, 5, 0, CardState.REVIEW), rating, TODAY)

    assert result.ease_factor == pytest.approx(expected_ease, abs=1e-4)


def test_ease_factor_never_drops_below_floor() -> None:
    """Sàn 1.3, dù bấm Lại liên tục."""
    card = make_card(1.4, 10, 5, 0, CardState.REVIEW)

    for _ in range(10):
        result = next_schedule(card, Rating.AGAIN, TODAY)
        card.ease_factor = result.ease_factor
        card.interval_days = result.interval_days
        card.repetitions = result.repetitions
        card.lapses = result.lapses

    assert card.ease_factor == 1.3


def test_press_again() -> None:
    """interval về 1, repetitions về 0, lapses tăng, state RELEARNING."""
    result = next_schedule(make_card(2.5, 30, 4, 2, CardState.REVIEW), Rating.AGAIN, TODAY)

    assert result.interval_days == 1
    assert result.repetitions == 0
    assert result.lapses == 3
    assert result.state is CardState.RELEARNING
    assert result.due_date == TODAY + timedelta(days=1)


def test_press_hard() -> None:
    """interval × 1.2, repetitions vẫn tăng, lapses không đổi."""
    result = next_schedule(make_card(2.5, 10, 4, 2, CardState.REVIEW), Rating.HARD, TODAY)

    assert result.interval_days == 12
    assert result.repetitions == 5
    assert result.lapses == 2
    assert result.state is CardState.REVIEW


@pytest.mark.parametrize(
    ("repetitions", "interval", "expected"),
    [
        (0, 0, 1),  # thẻ mới → 1 ngày
        (1, 1, 6),  # lượt thứ hai → 6 ngày
        (2, 6, 15),  # lượt thứ ba trở đi → round(6 × 2.5)
    ],
)
def test_press_good(repetitions: int, interval: int, expected: int) -> None:
    """1 ngày → 6 ngày → nhân EF."""
    card_state = CardState.NEW if repetitions == 0 else CardState.REVIEW
    result = next_schedule(
        make_card(2.5, interval, repetitions, 0, card_state), Rating.GOOD, TODAY
    )

    assert result.interval_days == expected
    assert result.repetitions == repetitions + 1
    assert result.state is CardState.REVIEW


def test_press_easy_on_already_reviewed_card() -> None:
    """Nhân EF MỚI rồi nhân thêm 1.3: EF mới = 2.6 → round(6 × 2.6) = 16 → round(16 × 1.3) = 21."""
    result = next_schedule(make_card(2.5, 6, 2, 0, CardState.REVIEW), Rating.EASY, TODAY)

    assert result.ease_factor == pytest.approx(2.6, abs=1e-4)
    assert result.interval_days == 21


def test_press_easy_on_new_card_still_gives_one_day() -> None:
    """round(1 × 1.3) = 1 — đúng spec, không phải bug."""
    result = next_schedule(make_card(2.5, 0, 0, 0, CardState.NEW), Rating.EASY, TODAY)

    assert result.interval_days == 1


def test_interval_never_smaller_than_one() -> None:
    """round(0 × 1.2) = 0 → nâng lên 1."""
    result = next_schedule(make_card(2.5, 0, 3, 0, CardState.NEW), Rating.HARD, TODAY)

    assert result.interval_days == 1


def test_relearning_card_pressed_good_returns_to_review() -> None:
    result = next_schedule(make_card(2.0, 1, 0, 1, CardState.RELEARNING), Rating.GOOD, TODAY)

    assert result.state is CardState.REVIEW
    assert result.interval_days == 1  # repetitions về 1 → 1 ngày


# ── Hai ca dưới đây KHÔNG có trong bộ test Java ────────────────────────────────
# Chúng canh một lớp lỗi chỉ tồn tại ở bản Python.


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [(0.5, 1), (1.5, 2), (2.5, 3), (12.5, 13), (16.5, 17), (-0.5, 0), (15.4, 15), (15.6, 16)],
)
def test_rounds_half_up_like_java(raw_value: float, expected: int) -> None:
    """`Math.round` của Java là `floor(x + 0.5)`; `round()` của Python làm tròn về số CHẴN.

    `round(2.5)` ra 2 ở Python nhưng 3 ở Java. Không ca nào trong bộ test Java chạm đúng
    biên `.5`, nên lỗi này sẽ đi lọt qua toàn bộ bản port và chỉ hiện ra dưới dạng lịch ôn
    lệch dần một ngày so với backend cũ — không có gì đỏ, không ai báo.
    """
    assert _round_half_up(raw_value) == expected


def test_half_day_boundary_in_the_real_formula() -> None:
    """Ca chạm biên đi qua đúng đường tính thật, không chỉ qua hàm làm tròn.

    interval 5 × EF 2.5 = 12.5 → Java cho 13. Python `round()` sẽ cho 12.
    """
    result = next_schedule(make_card(2.5, 5, 3, 0, CardState.REVIEW), Rating.GOOD, TODAY)

    assert result.interval_days == 13
    assert result.due_date == TODAY + timedelta(days=13)
