"""Đếm lượt gọi Gemini. Toàn bộ việc đếm nằm trong một câu SQL duy nhất."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

_UPSERT = text(
    """
    INSERT INTO gemini_usage (user_id, day, calls) VALUES (:user_id, :day, 1)
    ON CONFLICT (user_id, day) DO UPDATE SET calls = gemini_usage.calls + 1
    RETURNING calls
    """
)


def increment_and_get(db: Session, user_id: int, day: date) -> int:
    """Tăng bộ đếm và trả về giá trị SAU khi tăng, trong đúng MỘT câu lệnh.

    Đọc-rồi-ghi ở tầng Python sẽ hỏng thật: hai request song song cùng đọc ra một số rồi
    cùng ghi đè, và hạn mức trở thành gợi ý. `ON CONFLICT ... RETURNING` thì atomic.
    """
    return int(db.execute(_UPSERT, {"user_id": user_id, "day": day}).scalar_one())
