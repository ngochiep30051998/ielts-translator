"""DTO của màn thống kê. KHÔNG có SQLAlchemy entity nào ở đây — tính năng này không tạo bảng.

Dùng `import datetime` rồi annotate `datetime.date` thay vì `from datetime import date`: DTO
có field tên đúng là `date`, và `date: date` tuy chạy được vẫn là thứ khiến người đọc phải
dừng lại kiểm tra xem cái nào là kiểu, cái nào là tên.
"""

from __future__ import annotations

import datetime

from app.common.schema import ApiModel
from app.quiz.models import QuizType


class DailyPoint(ApiModel):
    """Một ô ngày. `reviews = 0` nghĩa là ngày đó không ôn — KHÔNG phải thiếu dữ liệu."""

    date: datetime.date
    reviews: int


class StreakDto(ApiModel):
    """`current` và `longest` là hai con số khác nhau; `lastActiveDate` là None khi chưa ôn
    lần nào."""

    current: int
    longest: int
    last_active_date: datetime.date | None


class TotalsDto(ApiModel):
    """Toàn bộ lịch sử, không giới hạn cửa sổ — đây là màn động lực, con số phải to lên mãi."""

    reviews: int
    learned_words: int
    active_days: int


class RecallDto(ApiModel):
    """Số lượt THÔ theo bốn mức tự chấm. Tỉ lệ nhớ là `1 − again/tổng`, client tự tính — trả
    sẵn cả hai là dựng hai nguồn sự thật cho cùng một con số."""

    again: int
    hard: int
    good: int
    easy: int


class QuizTypeStatsDto(ApiModel):
    """`avgScore` là None với `FILL_BLANK` và `COLLOCATION_CHOICE`: hai loại đó chấm 100 hoặc
    0 nên điểm trung bình chỉ là `correct/attempts` viết lại. None ở đây nghĩa là "loại này
    không có khái niệm điểm", cùng ngữ nghĩa `improvedVersion` trong `AnswerResultDto`."""

    type: QuizType
    attempts: int
    correct: int
    avg_score: int | None


class StatsDto(ApiModel):
    """`daily` LUÔN đúng 91 phần tử; `quiz` LUÔN đúng 3 phần tử theo thứ tự khai báo của
    `QuizType`. Hai bất biến đó là hợp đồng — UI dựa vào để không phải phân nhánh "thiếu dữ
    liệu" ở bốn chỗ."""

    streak: StreakDto
    totals: TotalsDto
    daily: list[DailyPoint]
    recall: RecallDto
    quiz: list[QuizTypeStatsDto]
