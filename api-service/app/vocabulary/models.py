"""Entity và DTO của context vocabulary."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field, field_serializer, field_validator
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.schema import ApiModel
from app.db import Base


class VocabEntry(Base):
    __tablename__ = "vocab_entry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    #: Chủ sở hữu. Đây là cột user_id DUY NHẤT của toàn bộ dữ liệu học — srs_card,
    #: srs_distractor, quiz_item đều treo vào entry này, review_log treo vào srs_card,
    #: quiz_attempt treo vào quiz_item. Suy ra được thì đừng nhân bản: hai nguồn sự thật
    #: lệch nhau ở đây nghĩa là dữ liệu người này lọt sang người kia, im lặng.
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )

    term: Mapped[str] = mapped_column(Text, nullable=False)
    lemma: Mapped[str | None] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(String(8), nullable=False)
    pos: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    ipa: Mapped[str | None] = mapped_column(Text)
    meaning_vi: Mapped[str] = mapped_column(Text, nullable=False)
    definition_en: Mapped[str | None] = mapped_column(Text)
    cefr: Mapped[str | None] = mapped_column(String(4))
    band_level: Mapped[str | None] = mapped_column(String(8))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_sentence: Mapped[str | None] = mapped_column(Text)
    collocations: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    examples: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SaveVocabRequest(ApiModel):
    term: str = Field(min_length=1)
    lemma: str | None = None
    lang: str = Field(min_length=1)
    pos: str | None = None
    ipa: str | None = None
    meaning_vi: str = Field(min_length=1)
    definition_en: str | None = None
    cefr: str | None = None
    band_level: str | None = None
    tags: list[str] | None = None
    source_url: str | None = None
    source_sentence: str | None = None
    collocations: Any = None
    examples: Any = None

    @field_validator("term", "lang", "meaning_vi")
    @classmethod
    def khong_duoc_de_trong(cls, value: str) -> str:
        """Bản dịch của `@NotBlank` trên `term`/`lang`/`meaningVi`.

        `min_length=1` một mình vẫn cho `"   "` lọt qua, còn `@NotBlank` bên Java thì không.
        Không có nhánh này thì một lượt bôi đen trúng khoảng trắng sẽ tạo ra một hàng
        `vocab_entry` rỗng — kèm cả một thẻ ôn tập cho nó — mà không có gì đỏ ở đâu cả.

        Giữ nguyên chữ "không được để trống": đây đúng message của `@NotBlank` bên Java, và
        bubble hiển thị thẳng `message` từ backend.
        """
        if not value.strip():
            raise ValueError("không được để trống")
        return value


class SaveVocabResponse(ApiModel):
    id: int
    already_exists: bool


class VocabEntryDto(ApiModel):
    id: int
    term: str
    lemma: str | None
    lang: str
    pos: str
    ipa: str | None
    meaning_vi: str | None
    definition_en: str | None
    cefr: str | None
    band_level: str | None
    tags: list[str]
    source_url: str | None
    source_sentence: str | None
    collocations: Any
    examples: Any
    created_at: datetime

    @field_serializer("created_at", when_used="json")
    def _created_at_utc(self, value: datetime) -> datetime:
        """Luôn phát ra mốc thời gian ở UTC (`...Z`), không theo múi giờ của máy chủ.

        Postgres trả TIMESTAMPTZ theo timezone của phiên kết nối, nên nếu không quy về UTC ở
        đây thì cùng một hàng dữ liệu phát ra `+07:00` trên máy dev và `Z` trên server —
        `createdAt` bên Java là `Instant`, Jackson luôn in `Z`. Extension đọc chuỗi này bằng
        `new Date(...)` nên cả hai dạng đều parse được, nhưng bất kỳ chỗ nào so sánh chuỗi
        (sắp xếp, khoá cache, so hai bản export) sẽ lệch một cách khó thấy.
        """
        return value.astimezone(UTC)


class VocabPage(ApiModel):
    """Một trang sổ từ — bản thay `Page<VocabEntryDto>` của Spring Data.

    Chỉ giữ những field VÔ HƯỚNG mà `PageResponse<T>` bên `shared/types.ts` đọc, cộng vài
    field suy ra được của Spring. Cố ý BỎ `pageable` và `sort`: chúng là chi tiết nội bộ của
    Spring Data mà extension chưa từng chạm tới, và Spring Boot 3.x còn cảnh báo rằng hình
    dạng JSON của `PageImpl` không ổn định giữa các phiên bản. Dựng lại một cấu trúc không
    ai đọc, chỉ để giống một thứ mà chính tác giả nó nói là đừng dựa vào, là công vô ích.
    """

    content: list[VocabEntryDto]
    total_elements: int
    total_pages: int
    #: Chỉ số trang hiện tại, tính từ 0. Tên `number` là tên Spring phát ra, giữ nguyên.
    number: int
    size: int
    number_of_elements: int
    first: bool
    last: bool
    empty: bool
