"""`TZ` là tên biến bị nền tảng chiếm — cấu hình múi giờ phải sống sót được điều đó.

Sự cố có thật trên production: `GET /api/stats` trả 500 với
`ZoneInfoNotFoundError: 'No time zone found with key :UTC'`.

Chuỗi nhân quả:

1. Vercel chạy trên AWS Lambda, và Lambda **tự đặt** biến môi trường `TZ=:UTC` — dạng POSIX
   có dấu hai chấm đầu, không phải key IANA.
2. `Settings.tz` đọc đúng tên biến đó nên nhận `":UTC"`, đè mặc định `Asia/Ho_Chi_Minh`.
3. `ZoneInfo(":UTC")` không tra được → `ZoneInfoNotFoundError`.
4. Không sửa được từ dashboard: Vercel từ chối biến tên `TZ` ("The name of your Environment
   Variable is reserved"). Đây là điểm quan trọng nhất — **cấu hình không phải là lối thoát**,
   nên lối thoát phải nằm trong code: một tên biến thứ hai (`APP_TZ`) và một luật bỏ qua giá
   trị của nền tảng.

Không mô phỏng được bằng cách đặt `TZ` rồi gọi `time.tzset()`: thứ hỏng ở đây là *giá trị đọc
vào Settings*, không phải giờ của tiến trình.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest

from app.config import TZ_MAC_DINH, Settings


@pytest.fixture(autouse=True)
def _env_khong_co_tz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Máy dev có thể đang đặt sẵn `TZ`; biến môi trường thắng cả `_env_file=None`."""
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.delenv("APP_TZ", raising=False)


def test_tz_cua_lambda_bi_bo_qua_thay_vi_lam_chet_stats() -> None:
    """`:UTC` là dấu vết của nền tảng, không phải cấu hình của người dùng."""
    settings = Settings(_env_file=None, TZ=":UTC")  # type: ignore[call-arg]

    assert settings.tz == TZ_MAC_DINH
    ZoneInfo(settings.tz)  # không được ném — đây chính là dòng đã nổ trên production


def test_khong_cat_dau_hai_cham_de_thanh_utc() -> None:
    """Cắt `:` cho ra `UTC` — một key HỢP LỆ, và đó mới là cái bẫy.

    App sẽ chạy tiếp, không lỗi gì, chỉ là "hôm nay" lệch 7 tiếng so với giờ VN: heatmap trỏ
    sai ô và streak đứt sai ngày trong 7 giờ mỗi ngày. Lỗi âm thầm khó phát hiện hơn hẳn 500,
    nên thà quay về mặc định.
    """
    assert Settings(_env_file=None, TZ=":UTC").tz != "UTC"  # type: ignore[call-arg]


def test_app_tz_thang_tz_cua_nen_tang(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trên Vercel người dùng chỉ đặt được `APP_TZ`, và nó phải thắng `TZ` mà Lambda áp đặt."""
    monkeypatch.setenv("TZ", ":UTC")
    monkeypatch.setenv("APP_TZ", "Europe/Paris")

    assert Settings(_env_file=None).tz == "Europe/Paris"  # type: ignore[call-arg]


def test_tz_van_con_tac_dung_cho_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đường Docker không đổi: `docker-compose.yml` truyền `TZ` để chỉnh cả đồng hồ container,
    và app phải đọc đúng biến đó — nếu không, giờ container và `settings.tz` trôi khỏi nhau."""
    monkeypatch.setenv("TZ", "Europe/Paris")

    assert Settings(_env_file=None).tz == "Europe/Paris"  # type: ignore[call-arg]


def test_tz_rong_quay_ve_mac_dinh() -> None:
    """`TZ=` (đặt nhưng bỏ trống) là cấu hình lỡ tay, không phải yêu cầu chạy giờ UTC."""
    assert Settings(_env_file=None, TZ="   ").tz == TZ_MAC_DINH  # type: ignore[call-arg]


def test_mac_dinh_la_key_iana_that() -> None:
    """Mặc định phải tra được — nó là thứ mọi nhánh fallback ở trên rơi về."""
    ZoneInfo(Settings(_env_file=None).tz)  # type: ignore[call-arg]
