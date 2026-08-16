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
    #: Số lượt luyện thêm trong ngày. Field RIÊNG chứ không cộng vào `reviews`: `reviews`
    #: giữ nguyên nghĩa cũ (chỉ lượt theo lịch), nên mọi test thống kê cũ phải xanh nguyên.
    practice: int


class StreakDto(ApiModel):
    """`current` và `longest` là hai con số khác nhau; `lastActiveDate` là None khi chưa ôn
    lần nào."""

    current: int
    longest: int
    last_active_date: datetime.date | None


class TotalsDto(ApiModel):
    """Toàn bộ lịch sử, không giới hạn cửa sổ — đây là màn động lực, con số phải to lên mãi.

    Hai ngoại lệ có chủ ý: `avgBand` là ảnh chụp hiện tại của cả sổ từ (không cộng dồn được),
    còn `introducedLast7` cố ý chỉ nhìn 7 ngày.

    Ba con số đếm TỪ ở đây đo ba thứ khác nhau, đừng dùng lẫn. Bất biến:
    `masteredWords + learningWords == learnedWords`; từ chưa ôn lượt nào không nằm trong con
    số nào cả.
    """

    reviews: int
    #: Số từ đã ôn ít nhất MỘT lượt (`repetitions >= 1`). Nhãn hiển thị là "từ đã học" ở
    #: StatsTab — KHÔNG phải "đã thuộc". Giữ nguyên nghĩa cũ, đừng gán nhãn "thuộc" cho nó.
    learned_words: int
    #: Số từ ĐÃ THUỘC (`repetitions >= MASTERED_REPETITIONS`) — ô xanh dương ở màn Hôm nay.
    #:
    #: Cùng một ngưỡng với `mastered` của từng chủ đề (`VocabTagDto`) và với thanh thành thạo
    #: phía frontend. Trước đây ô đó vẽ `learnedWords`, nên một từ mới ôn đúng một lượt làm
    #: màn hình vừa ghi "1 từ đã thuộc" vừa vẽ chủ đề của nó ở 0%.
    mastered_words: int
    #: Số từ ĐANG HỌC — `1 <= repetitions < MASTERED_REPETITIONS`.
    learning_words: int
    active_days: int
    #: Band trung bình của CẢ sổ từ (`vocab_entry.band_level`), làm tròn một chữ số thập phân.
    #:
    #: `None` nghĩa là chưa từ nào có band ĐỌC ĐƯỢC — khác hẳn `0.0`. UI phải hiện "—" cho ca
    #: đó: nói với người học rằng band trung bình của họ bằng 0 là một câu vừa sai vừa nản.
    avg_band: float | None
    #: Số TỪ lần đầu được đưa vào vòng ôn trong 7 ngày gần nhất, tính CẢ hôm nay, theo
    #: `settings.tz`. Nhãn hiển thị: "+N từ mới tuần này".
    #:
    #: KHÔNG phải "số từ đạt ngưỡng thuộc trong tuần" — con số đó KHÔNG tính được từ dữ liệu
    #: đang có: `review_log` không lưu `repetitions`, chỉ lưu `rating`, `reviewed_at`,
    #: `prev_interval`, `new_interval`, `mode`. Đừng đặt nó dưới ô "đã thuộc" như phần tăng
    #: thêm của con số đó; nó là một phép đo riêng, và một thẻ bấm "Lại" vẫn được tính vì nó
    #: THẬT SỰ đã bước vào vòng ôn.
    introduced_last7: int


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
