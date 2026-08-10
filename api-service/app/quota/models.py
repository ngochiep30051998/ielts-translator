"""Entity của context quota.

Tồn tại vì API key Gemini dùng CHUNG: một người làm 200 câu quiz là cả nhóm hết quota.
Entity này chỉ để schema nhìn thấy bảng — mọi thao tác đi qua câu SQL tường minh trong
`repository.py`, vì luật ở đây là một lượt UPSERT nguyên tử chứ không phải đọc-rồi-ghi.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GeminiUsage(Base):
    """Số lượt gọi Gemini của một người trong một ngày."""

    __tablename__ = "gemini_usage"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
