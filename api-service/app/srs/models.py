"""Entity, enum và DTO của context srs."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.schema import ApiModel
from app.db import Base


class CardState(enum.StrEnum):
    """NEW: chưa ôn lần nào. REVIEW: đang trong chu kỳ bình thường. RELEARNING: vừa quên."""

    NEW = "NEW"
    REVIEW = "REVIEW"
    RELEARNING = "RELEARNING"


class Rating(enum.StrEnum):
    """Mức độ nhớ người dùng tự chấm sau khi lật thẻ. `q` dùng trong công thức EF của SM-2."""

    AGAIN = "AGAIN"
    HARD = "HARD"
    GOOD = "GOOD"
    EASY = "EASY"

    @property
    def q(self) -> int:
        return {"AGAIN": 0, "HARD": 1, "GOOD": 2, "EASY": 3}[self.value]


class ReviewMode(enum.StrEnum):
    """Phân biệt hai loại lượt ôn. Ghi nhầm loại KHÔNG làm gì đỏ — nó chỉ lặng lẽ làm sai
    streak và tỉ lệ nhớ ở tab Thống kê, hoặc phá lịch SM-2."""

    #: Lượt ôn theo lịch — ĐỔI due_date, interval_days, ease_factor, repetitions.
    SCHEDULED = "SCHEDULED"
    #: Luyện thêm — KHÔNG đụng gì tới lịch.
    PRACTICE = "PRACTICE"


class SrsCard(Base):
    __tablename__ = "srs_card"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vocab_entry_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vocab_entry.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    ease_factor: Mapped[float] = mapped_column(Double, nullable=False, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReviewLog(Base):
    __tablename__ = "review_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    card_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("srs_card.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[str] = mapped_column(String(8), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    prev_interval: Mapped[int] = mapped_column(Integer, nullable=False)
    new_interval: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)


class SrsDistractor(Base):
    """Mồi nhử cho câu trắc nghiệm ôn tập, do Gemini sinh một lần rồi cache.

    `prompt_version` theo đúng nguyên tắc của `lookup_cache`: sửa prompt phải tăng version
    trong file, bản ghi version cũ coi như không có và sẽ được sinh lại.
    """

    __tablename__ = "srs_distractor"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vocab_entry_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vocab_entry.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    vi_options: Mapped[Any] = mapped_column(JSONB, nullable=False)
    en_options: Mapped[Any] = mapped_column(JSONB, nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DistractorSet(ApiModel):
    """Ba mồi nhử cho mỗi chiều hỏi. `viOptions` là nghĩa tiếng Việt sai (dùng cho câu hỏi
    EN → VI), `enOptions` là từ tiếng Anh sai (dùng cho VI → EN)."""

    vi_options: list[str]
    en_options: list[str]


class CardDto(ApiModel):
    """Gộp sẵn dữ liệu vocab để side panel chỉ phải gọi một lượt cho cả xấp thẻ.

    `viDistractors` / `enDistractors` rỗng nghĩa là mồi nhử chưa sinh kịp; panel tự bù bằng
    thẻ khác trong hàng đợi chứ không coi đó là lỗi.
    """

    id: int
    vocab_entry_id: int
    term: str
    ipa: str | None
    pos: str | None
    meaning_vi: str | None
    definition_en: str | None
    cefr: str | None
    band_level: str | None
    collocations: Any
    examples: Any
    state: CardState
    due_date: date
    vi_distractors: list[str]
    en_distractors: list[str]


class ReviewRequest(ApiModel):
    card_id: int
    rating: Rating


class PracticeRequest(ApiModel):
    """Cùng hình dạng `ReviewRequest` nhưng là kiểu RIÊNG, không tái dùng.

    Hai request đi vào hai endpoint có hậu quả khác hẳn nhau — một cái đổi lịch, một cái
    không. Dùng chung một kiểu làm chỗ khác biệt đó biến mất khỏi chữ ký hàm."""

    card_id: int
    rating: Rating


class ReviewResponse(ApiModel):
    next_due_date: date
    interval_days: int
    ease_factor: float


class SrsStatsDto(ApiModel):
    """`dueCount` là số thẻ người dùng thực sự phải ôn hôm nay — đã cộng phần thẻ mới còn
    được phép học. Đây là con số hiện trên badge.

    `newCount` là tổng số thẻ NEW, không trừ giới hạn ngày. `learnedCount` là số thẻ đã ôn
    ít nhất một lượt.
    """

    due_count: int
    new_count: int
    learned_count: int
