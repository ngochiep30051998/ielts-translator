"""Entity, enum và DTO của context quiz."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import Field, model_validator
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.schema import ApiModel
from app.db import Base


class QuizType(enum.StrEnum):
    """Ba loại quiz. Tên hằng đi thẳng vào cột `quiz_item.type` và vào JSON API."""

    #: Gemini sinh câu chứa từ, che từ đích bằng "___". Chấm local.
    FILL_BLANK = "FILL_BLANK"
    #: Gemini sinh 1 đáp án đúng + 3 mồi nhử. Chấm local bằng so index.
    COLLOCATION_CHOICE = "COLLOCATION_CHOICE"
    #: Đề bài là chính từ đó, không tốn call sinh đề. Gemini chấm.
    FREE_WRITE = "FREE_WRITE"


class QuizItem(Base):
    __tablename__ = "quiz_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vocab_entry_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vocab_entry.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class QuizAttempt(Base):
    """`correct` tách khỏi `score` vì score một mình không phân biệt được "sai" (score = 0)
    với "chưa chấm".

    `improved_version` tách riêng khỏi `ai_feedback` vì hợp đồng API trả hai trường khác
    nhau. NULL với FILL_BLANK và COLLOCATION_CHOICE — hai loại đó không có khái niệm câu
    viết lại.
    """

    __tablename__ = "quiz_attempt"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    quiz_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quiz_item.id", ondelete="CASCADE"), nullable=False
    )
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_feedback: Mapped[str | None] = mapped_column(Text)
    improved_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GenerateQuizRequest(ApiModel):
    """Sinh đề cho ĐÚNG MỘT loại. Panel muốn nhiều loại thì gửi nhiều request TUẦN TỰ.

    Vì sao một loại mỗi request: mỗi loại là một lượt gọi Gemini, mà một lượt gọi xấu nhất
    mất 2 × 30s + 1s backoff = 61s (`MAX_ATTEMPTS = 2`). Gộp ba loại vào một request đẩy
    trường hợp xấu nhất lên ~122s, vượt mọi ngưỡng chờ hợp lý phía client, và biến một loại
    hỏng thành mất trắng cả đề.
    """

    #: Danh sách id từ chỉ định thẳng; bỏ qua điều kiện repetitions >= 1. Thiếu field ≡
    #: None. Id không tồn tại thì bỏ qua, không lỗi.
    vocab_ids: list[int] | None = Field(default=None, min_length=1, max_length=50)
    #: Số CÂU muốn sinh cho loại này. Mỗi từ sinh đúng 1 câu cho 1 loại, nên đây cũng đúng
    #: bằng số từ được chọn.
    count: int | None = Field(default=None, ge=1, le=50)
    type: QuizType

    @model_validator(mode="after")
    def exactly_one_selector(self) -> GenerateQuizRequest:
        """Đúng MỘT trong `vocabIds` / `count` được cung cấp.

        Ràng buộc diễn đạt bằng validator của Pydantic chứ không bằng `AppError`: request
        sai phải là HTTP 400. Handler `RequestValidationError` trả 400; còn
        `AppError.of(ErrorCode.INTERNAL, …)` lại rơi vào `status_for()` và trả 500 — sai
        ngữ nghĩa.
        """
        has_ids = self.vocab_ids is not None and len(self.vocab_ids) > 0
        has_count = self.count is not None
        if has_ids == has_count:
            raise ValueError("phải cung cấp đúng một trong vocabIds hoặc count")
        return self


class QuizItemDto(ApiModel):
    """Đề bài gửi xuống panel. TUYỆT ĐỐI không chứa đáp án dưới bất kỳ dạng nào.

    Người dùng nộp qua POST /api/quiz/answer và backend mới là nơi so đáp án.

    Vì sao `term` là None với FILL_BLANK: đáp án của FILL_BLANK chính là dạng đã bị che của
    `term` — đa số trường hợp là chuỗi giống hệt. Gửi kèm `term` là gửi luôn đáp án, dù
    `payload.answer` không nằm trong DTO.

    Mọi khoá LUÔN có mặt kể cả khi giá trị là None: mirror TypeScript khai `string | null`
    chứ không phải optional, hai bên chỉ khớp khi khoá luôn có mặt.
    """

    id: int
    type: QuizType
    vocab_entry_id: int
    #: None với FILL_BLANK; non-None với COLLOCATION_CHOICE và FREE_WRITE.
    term: str | None
    #: LUÔN non-None và khác rỗng với cả ba loại.
    question: str
    #: Câu chứa "___"; non-None CHỈ với FILL_BLANK.
    sentence: str | None
    #: Đúng 4 lựa chọn ĐÃ XÁO TRỘN SẴN lúc lưu item; non-None CHỈ với COLLOCATION_CHOICE.
    #: Thứ tự này là thứ tự đã lưu trong DB — không xáo lại lúc trả response, và panel
    #: KHÔNG được xáo lại, vì câu trả lời là index trong chính mảng này.
    options: list[str] | None


class AnswerQuizRequest(ApiModel):
    """`answer` LUÔN là string trên đường truyền, cho cả ba loại.

    Với COLLOCATION_CHOICE đây là index 0-based dạng chuỗi ("0".."3"); backend tự parse.
    Chuỗi không parse được thành index hợp lệ tính là TRẢ LỜI SAI, không phải lỗi request.

    Không đặt ràng buộc "khác rỗng": chuỗi rỗng là GIÁ TRỊ HỢP LỆ, nghĩa là "bỏ qua câu
    này". Người học không nghĩ ra từ rồi bấm Nộp là thao tác học tập bình thường; bắt lỗi ở
    đây biến nó thành 400 VÀ không ghi dòng `quiz_attempt` nào, nên câu đó lại hiện ở đề sau
    như chưa từng làm.

    Độ dài KHÔNG chặn ở đây mà bằng kiểm tra thủ công trong service, để ném TEXT_TOO_LONG
    (400, đúng ngữ nghĩa) thay vì INTERNAL — cùng cách translation làm với MAX_TEXT_LENGTH.
    """

    quiz_item_id: int
    answer: str


class AnswerResultDto(ApiModel):
    """Kết quả chấm một câu.

    `correct` — FILL_BLANK / COLLOCATION_CHOICE: so khớp đúng hay sai. FREE_WRITE:
    `meaning_ok && grammar_ok` do Gemini trả. `band_ok` CỐ Ý không tham gia — nhãn band là
    gợi ý tham khảo, không phải sự thật.

    `score` — FILL_BLANK / COLLOCATION_CHOICE: đúng 100 hoặc đúng 0. FREE_WRITE: 0–100 do
    Gemini trả.

    `feedback` — LUÔN non-None và khác rỗng, tiếng Việt. Với FILL_BLANK và
    COLLOCATION_CHOICE khi trả lời SAI, chuỗi này CHỨA LUÔN đáp án đúng — đó là cách duy
    nhất người học biết đáp án, vì `QuizItemDto` không mang nó.

    `improvedVersion` — CHỈ FREE_WRITE mới có. Với hai loại kia LUÔN None: không phải "chưa
    có", mà là "loại này không có khái niệm câu viết lại". Panel không được render khối đó
    khi None.
    """

    correct: bool
    score: int
    feedback: str
    improved_version: str | None


class ExplainQuizRequest(ApiModel):
    """CỐ Ý chỉ mang `quizItemId` và không nhận câu trả lời từ client.

    Response của endpoint này TIẾT LỘ ĐÁP ÁN, nên nó phải tự đọc `quiz_attempt` gần nhất và
    từ chối khi chưa có lượt làm nào. Nhận câu trả lời do client gửi lên rồi tin luôn là
    biến `/explain` thành đường vòng đọc đáp án trước khi trả lời — đúng thứ mà `QuizItemDto`
    cố ý bảo vệ.
    """

    quiz_item_id: int


class ExplanationDto(ApiModel):
    """Giải thích một câu ĐÃ trả lời. KHÔNG lưu xuống DB — sinh lúc người học bấm nút và chỉ
    sống trong đúng một response.

    `sentenceEn` và `sentenceVi` là CẶP ĐÔI: cùng None hoặc cùng non-None, không bao giờ một
    nửa. Cùng None xảy ra đúng một ca — FREE_WRITE bị bỏ qua nên không có câu nào để dịch.
    """

    #: LUÔN non-None và khác rỗng, tiếng Việt. Bám theo câu trả lời của người học khi họ có
    #: trả lời; chỉ giải thích đáp án khi họ bỏ qua.
    explanation: str
    #: LUÔN non-None và khác rỗng. Nghĩa tiếng Việt của từ/cụm đáp án trong đúng ngữ cảnh câu.
    answer_meaning: str
    sentence_en: str | None
    sentence_vi: str | None
