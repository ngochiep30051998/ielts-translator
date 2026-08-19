"""Hạn mức gọi Gemini theo từng người, mỗi ngày.

Gọi NGAY TRƯỚC mỗi `generate_json` và SAU khi đã tra cache — cache hit không chạm Gemini
nên tính vào hạn mức là phạt oan.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.config import Settings, get_settings
from app.quota import repository as repo


def consume(db: Session, user_id: int, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    daily_limit = cfg.auth_daily_gemini_calls
    if daily_limit <= 0:
        return  # 0 hoặc âm = tắt hạn mức, dùng cho môi trường dev

    # `now().date()` theo giờ HỆ THỐNG chứ không phải UTC — cùng cách `LocalDate.now()` bên
    # Java làm, và cùng lý do TZ được truyền vào container: ngày phải đổi lúc nửa đêm giờ
    # Việt Nam, không phải 07:00 sáng.
    used = repo.increment_and_get(db, user_id, datetime.now().date())
    if used > daily_limit:
        # GEMINI_QUOTA chứ không đẻ mã mới: UI đã biết hiển thị mã này, và với người dùng
        # thì "hết lượt hôm nay" đúng là hết quota.
        raise AppError.of(
            ErrorCode.GEMINI_QUOTA, f"Đã dùng hết {daily_limit} lượt AI của hôm nay"
        )
