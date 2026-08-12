"""Unit test cho `_hom_nay()` — hàm xác định "hôm nay" theo múi giờ cấu hình.

`_hom_nay()` PHẢI đọc `settings.tz`, không phải giờ hệ thống của tiến trình đang chạy (xem
docstring của nó trong `app/stats/service.py`). Trên máy dev và trên CI, biến môi trường `TZ`
thường trùng với `settings.tz` mặc định (`Asia/Ho_Chi_Minh`), nên `datetime.now(...).date()`
kiểu tiến trình và `_hom_nay()` luôn cho cùng một ngày — một bài test ngây thơ (gọi
`_hom_nay()` một lần rồi so với `date.today()`) sẽ không bao giờ đỏ dù ai đó âm thầm thay
`_hom_nay()` bằng `date.today()`. Chỗ duy nhất hai thứ lệch nhau là môi trường không đặt `TZ`
(Vercel) — không mô phỏng lại được bằng `monkeypatch.setenv("TZ", ...)` vì tiến trình Python
không đọc lại `TZ` sau khi khởi động (không gọi `time.tzset()`).

Cách kiểm tất định, không phụ thuộc giờ chạy test: ép `settings.tz` lần lượt sang hai múi giờ
cách nhau hơn 24 tiếng — Kiritimati (UTC+14) và Niue (UTC-11) — rồi khẳng định `_hom_nay()`
cho ra hai ngày khác nhau. Vì chênh lệch giữa hai múi giờ này luôn ≥ 24 tiếng, ngày địa
phương của chúng khác nhau ở MỌI thời điểm trong ngày, nên nếu `_hom_nay()` bị đơn giản hoá
thành `date.today()` (bỏ qua `settings.tz`), hai lần gọi sẽ luôn trả cùng một ngày và
assertion dưới đây đỏ ở 100% số lần chạy — không có giờ nào trong ngày mà test này xanh nhầm.
"""

from __future__ import annotations

import pytest

import app.stats.service as stats_service
from app.config import Settings


def _settings_voi_tz(tz: str) -> Settings:
    return Settings(TZ=tz)  # type: ignore[call-arg]


def test_hom_nay_theo_tz_cua_settings_khong_theo_gio_tien_trinh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stats_service, "get_settings", lambda: _settings_voi_tz("Pacific/Kiritimati")
    )
    ngay_kiritimati = stats_service._hom_nay()

    monkeypatch.setattr(stats_service, "get_settings", lambda: _settings_voi_tz("Pacific/Niue"))
    ngay_niue = stats_service._hom_nay()

    # UTC+14 và UTC-11 cách nhau 25 tiếng nên ngày địa phương luôn lệch nhau — không có thời
    # điểm nào trong ngày mà hai giá trị này trùng nhau.
    assert ngay_kiritimati != ngay_niue
