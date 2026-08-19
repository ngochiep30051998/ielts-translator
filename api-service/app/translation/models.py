"""Entity, enum và DTO của context translation."""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.schema import ApiModel
from app.db import Base

#: Lớp ký tự viết TAY chứ không dùng `\s`. `\s` của Python bao cả khoảng trắng Unicode, mà
#: `\s` của Java thì không — và U+00A0 (`&nbsp;`) nhan nhản trong text bôi đen từ web. Một
#: cụm bốn chữ nối bằng `&nbsp;` sẽ ra WORD ở bản Java và SENTENCE ở đây: hai hình dạng
#: payload khác nhau cho cùng một chuỗi, và hai khoá cache khác nhau.
_WHITESPACE = re.compile(r"[ \t\n\x0b\f\r]+")


class Direction(enum.StrEnum):
    EN_VI = "EN_VI"
    VI_EN = "VI_EN"


class Mode(enum.StrEnum):
    WORD = "WORD"
    SENTENCE = "SENTENCE"

    @staticmethod
    def of(text: str | None) -> Mode:
        """Từ 3 token trở xuống coi là tra từ; nhiều hơn là tra câu."""
        if text is None:
            return Mode.WORD
        # Cắt rìa bằng đúng bộ ký tự của `_WHITESPACE`, cùng lý do như ở đó.
        trimmed = text.strip(" \t\n\x0b\f\r")
        if not trimmed:
            return Mode.WORD
        tokens = len(_WHITESPACE.split(trimmed))
        return Mode.WORD if tokens <= 3 else Mode.SENTENCE


class LookupCache(Base):
    """Cache bản dịch của một chuỗi công khai.

    CỐ Ý không có `user_id` (ràng buộc #14): dùng chung là phần tiết kiệm quota Gemini lớn
    nhất của hệ thống, và nội dung ở đây không chứa gì riêng tư. "Sửa cho nhất quán" với các
    bảng khác là làm hỏng đúng chỗ nó đang có ích.
    """

    __tablename__ = "lookup_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    response: Mapped[Any] = mapped_column(JSONB, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TranslateRequest(ApiModel):
    text: str = Field(min_length=1)
    context_sentence: str | None = None
    source_url: str | None = None
    page_title: str | None = None

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        """Bản dịch của `@NotBlank`: `min_length=1` một mình vẫn cho `"   "` lọt qua.

        Thông điệp phải là tiếng Việt và phải giữ nguyên chữ "không được để trống": bubble
        hiển thị thẳng `message` từ backend, và hợp đồng cũ của Spring trả 400 chứ không
        phải 422 (`main.py` lo phần status).
        """
        if not value.strip():
            raise ValueError("không được để trống")
        return value


class TranslateResponse(ApiModel):
    direction: Direction
    mode: Mode
    cached: bool
    payload: Any
