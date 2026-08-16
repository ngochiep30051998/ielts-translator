"""Entity và DTO của context vocabulary."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import Field, field_serializer, field_validator
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.schema import ApiModel
from app.db import Base
from app.srs.models import CardState


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


class VocabUpdateRequest(ApiModel):
    """Body của `PATCH /api/vocab/{id}` — PATCH chứ không PUT.

    Field VẮNG MẶT nghĩa là "không đổi", và đó là chỗ duy nhất trong dự án mà "không gửi"
    khác hẳn "gửi giá trị rỗng": `tags: []` là một yêu cầu thật (gỡ hết thẻ). Dùng `None`
    làm dấu hiệu "không đổi" thì hai ca đó gộp làm một và không còn cách nào gỡ thẻ.

    Phân biệt bằng `model_fields_set` của Pydantic v2 — nó ghi lại đúng những field CÓ MẶT
    trong body, không phải những field khác giá trị mặc định.

    `None` tường minh cũng tính là "không đổi": hợp đồng message phía client
    (`UpdateVocabRequest` trong `packages/core/src/messages.ts`) dùng `null` cho nghĩa đó,
    nên body gửi lên có thể mang khoá với giá trị `null`. An toàn vì `null` KHÔNG phải giá
    trị hợp lệ của field nào ở đây — `meaningVi` phải là chuỗi không rỗng, `tags` phải là
    mảng.
    """

    meaning_vi: str | None = None
    tags: list[str] | None = None

    @field_validator("meaning_vi")
    @classmethod
    def khong_duoc_de_trong(cls, value: str | None) -> str | None:
        """Giống `@NotBlank` bên `SaveVocabRequest`: sửa một từ thành nghĩa rỗng là làm hỏng
        chính dòng người dùng đang muốn sửa, không có đường quay lại từ UI."""
        if value is not None and not value.strip():
            raise ValueError("không được để trống")
        return value

    def co_gui(self, ten: Literal["meaning_vi", "tags"]) -> bool:
        """Field `ten` có mặt trong body VÀ không phải `null`.

        `Literal` chứ không `str`: tra bằng `getattr` nên một tên gõ sai sẽ lặng lẽ trả
        `False`, tức field đó vĩnh viễn không bao giờ được cập nhật và không có gì đỏ.
        """
        return ten in self.model_fields_set and getattr(self, ten) is not None


class VocabTagDto(ApiModel):
    """Một chủ đề kèm SỐ TỪ mang nó — không phải số dòng sau khi bung mảng `tags`."""

    tag: str
    count: int
    #: Trong `count` đó, bao nhiêu từ đã thuộc (`srs_card.repetitions >= MASTERED_REPETITIONS`).
    #: Luôn `<= count`.
    #:
    #: Trả SỐ ĐẾM chứ không trả sẵn phần trăm: tỉ lệ là một phép chia ở client, còn trả `%`
    #: là khoá cứng cách làm tròn vào API — hai chỗ hiển thị nó (ô chủ đề ở tab Sổ từ, card
    #: "Chủ đề đang yếu" ở màn Hôm nay) không bắt buộc phải làm tròn giống nhau.
    mastered: int


class VocabTagsResponse(ApiModel):
    """Toàn bộ hàng chip của tab Sổ từ trong MỘT lượt gọi: `Tất cả 128 · Chưa gắn 41 ·
    Môi trường 24 · …`

    `total` cố ý nằm ở đây chứ không lấy từ `totalElements` của `GET /api/vocab`: request đó
    mang theo bộ lọc `tag`/`untagged` đang bật, nên chip "Tất cả" sẽ đọc thành đúng con số
    của chủ đề vừa bấm — con số đường-về bằng con số đang đứng cạnh nó.

    Ba con số lấy cùng một lượt vì hàng chip là MỘT đơn vị hiển thị: ghép nó từ hai request
    là mở đường cho hai nửa lệch nhau trên màn hình (một lượt xoá từ chen vào giữa là đủ).
    """

    #: Tổng số từ trong sổ, KHÔNG lọc gì.
    total: int
    #: Số từ có `tags` là mảng RỖNG. Chip "Chưa gắn" chỉ được hiện khi số này > 0 — chip đếm
    #: 0 là một ô bấm vào ra danh sách rỗng.
    untagged: int
    tags: list[VocabTagDto]


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

    #: Trạng thái ôn tập, lấy từ `srs_card` qua LEFT JOIN — `vocab_entry` không giữ bản sao
    #: nào của ba con số này (một nguồn sự thật, ràng buộc #13 áp dụng cho cả dữ liệu SRS).
    #:
    #: CẢ BA cùng `None` nghĩa là "từ này chưa có thẻ ôn" — trạng thái thật và bình thường
    #: (từ `pos = 'phrase'` không được tạo thẻ). Đó KHÔNG phải "chưa tải xong", và UI phải
    #: phân biệt được: vẽ thanh thành thạo rỗng khác hẳn vẽ khung chờ.
    srs_state: CardState | None = None
    srs_due_date: date | None = None
    srs_repetitions: int | None = None

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
