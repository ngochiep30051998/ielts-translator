"""Unit test cho `_today()` — hàm xác định "hôm nay" theo múi giờ cấu hình.

`_today()` PHẢI đọc `settings.tz`, không phải giờ hệ thống của tiến trình đang chạy (xem
docstring của nó trong `app/stats/service.py`). Trên máy dev và trên CI, biến môi trường `TZ`
thường trùng với `settings.tz` mặc định (`Asia/Ho_Chi_Minh`), nên `datetime.now(...).date()`
kiểu tiến trình và `_today()` luôn cho cùng một ngày — một bài test ngây thơ (gọi
`_today()` một lần rồi so với `date.today()`) sẽ không bao giờ đỏ dù ai đó âm thầm thay
`_today()` bằng `date.today()`. Chỗ duy nhất hai thứ lệch nhau là môi trường không đặt `TZ`
(Vercel) — không mô phỏng lại được bằng `monkeypatch.setenv("TZ", ...)` vì tiến trình Python
không đọc lại `TZ` sau khi khởi động (không gọi `time.tzset()`).

Cách kiểm tất định, không phụ thuộc giờ chạy test: ép `settings.tz` lần lượt sang hai múi giờ
cách nhau hơn 24 tiếng — Kiritimati (UTC+14) và Niue (UTC-11) — rồi khẳng định `_today()`
cho ra hai ngày khác nhau. Vì chênh lệch giữa hai múi giờ này luôn ≥ 24 tiếng, ngày địa
phương của chúng khác nhau ở MỌI thời điểm trong ngày, nên nếu `_today()` bị đơn giản hoá
thành `date.today()` (bỏ qua `settings.tz`), hai lần gọi sẽ luôn trả cùng một ngày và
assertion dưới đây đỏ ở 100% số lần chạy — không có giờ nào trong ngày mà test này xanh nhầm.
"""

from __future__ import annotations

import pytest

import app.stats.service as stats_service
from app.config import Settings


def _settings_with_tz(tz: str) -> Settings:
    return Settings(TZ=tz)  # type: ignore[call-arg]


def test_today_follows_settings_tz_not_process_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stats_service, "get_settings", lambda: _settings_with_tz("Pacific/Kiritimati")
    )
    kiritimati_date = stats_service._today()

    monkeypatch.setattr(stats_service, "get_settings", lambda: _settings_with_tz("Pacific/Niue"))
    niue_date = stats_service._today()

    # UTC+14 và UTC-11 cách nhau 25 tiếng nên ngày địa phương luôn lệch nhau — không có thời
    # điểm nào trong ngày mà hai giá trị này trùng nhau.
    assert kiritimati_date != niue_date
