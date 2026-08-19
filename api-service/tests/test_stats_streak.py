"""Streak là hàm thuần — KHÔNG chạm DB, không fixture `db`/`client`.

`today` là tham số chứ không phải `date.today()` gọi bên trong: đó là điều kiện duy nhất để
test được "hôm nay chưa ôn thì streak vẫn tính từ hôm qua" mà không phải giả lập đồng hồ.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.stats.streak import compute_streak

TODAY = date(2026, 8, 11)


def _days_ago(day_count: int) -> date:
    return TODAY - timedelta(days=day_count)


def test_no_days_reviewed_yet() -> None:
    result = compute_streak([], TODAY)
    assert result.current == 0
    assert result.longest == 0
    assert result.last_active is None


def test_only_reviewed_today() -> None:
    result = compute_streak([TODAY], TODAY)
    assert result.current == 1
    assert result.longest == 1
    assert result.last_active == TODAY


def test_only_reviewed_yesterday_still_keeps_streak() -> None:
    """9 giờ sáng chưa kịp ôn mà thấy streak về 0 là sai, và sai đúng lúc phản tác dụng
    nhất. Streak chỉ đứt khi CẢ hôm nay lẫn hôm qua đều trống."""
    result = compute_streak([_days_ago(1)], TODAY)
    assert result.current == 1
    assert result.last_active == _days_ago(1)


def test_last_review_two_days_ago_breaks_streak() -> None:
    result = compute_streak([_days_ago(2)], TODAY)
    assert result.current == 0
    assert result.longest == 1
    assert result.last_active == _days_ago(2)


def test_three_consecutive_days_ending_today() -> None:
    result = compute_streak([_days_ago(2), _days_ago(1), TODAY], TODAY)
    assert result.current == 3
    assert result.longest == 3


def test_three_consecutive_days_ending_yesterday() -> None:
    result = compute_streak([_days_ago(3), _days_ago(2), _days_ago(1)], TODAY)
    assert result.current == 3
    assert result.longest == 3


def test_longest_streak_is_in_the_past() -> None:
    """current và longest là hai con số khác nhau — trả cùng một giá trị cho cả hai là lỗi
    dễ lọt nhất ở đây."""
    review_days = [_days_ago(n) for n in (20, 19, 18, 17, 16)] + [_days_ago(1), TODAY]
    result = compute_streak(sorted(review_days), TODAY)
    assert result.current == 2
    assert result.longest == 5
    assert result.last_active == TODAY


def test_single_day_one_year_ago() -> None:
    long_ago = TODAY - timedelta(days=365)
    result = compute_streak([long_ago], TODAY)
    assert result.current == 0
    assert result.longest == 1
    assert result.last_active == long_ago
