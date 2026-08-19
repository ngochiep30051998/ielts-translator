"""Ghép ba câu truy vấn và hàm streak thành một `StatsDto`."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import get_settings
from app.quiz.models import QuizType
from app.srs import repository as srs_repo
from app.stats import repository as repo
from app.stats.models import (
    DailyPoint,
    QuizTypeStatsDto,
    RecallDto,
    StatsDto,
    StreakDto,
    TotalsDto,
)
from app.stats.streak import compute_streak

#: Độ dài cửa sổ `daily`. 91 = 13 tuần chẵn. Đổi số này là đổi hợp đồng API — mirror
#: TypeScript và test đều dựa vào "đúng 91 phần tử".
WINDOW_DAYS = 91

#: Cửa sổ của `totals.introducedLast7` — dòng "+N từ mới tuần này". 7 ngày TÍNH CẢ hôm nay,
#: tức [hôm nay − 6 ; hôm nay].
INTRODUCED_WINDOW_DAYS = 7


def get_stats(db: Session, user_id: int) -> StatsDto:
    reviews_by_day = repo.count_reviews_by_day(db, user_id)
    today = _today()

    # BẪY: `reviews_by_day` chứa CẢ những ngày chỉ có lượt luyện thêm (scheduled = 0). Lấy
    # thẳng danh sách ngày từ đó là cho streak tính cả ngày chỉ luyện — phá đúng quy tắc
    # "streak đo kỷ luật theo lịch", mà không ai chạm vào `streak.py`.
    scheduled_review_days = [day for day, scheduled, _ in reviews_by_day if scheduled > 0]
    st = compute_streak(scheduled_review_days, today)

    scheduled_by_day = {day: scheduled for day, scheduled, _ in reviews_by_day}
    practice_by_day = {day: practice for day, _, practice in reviews_by_day}
    counts_by_rating = repo.count_reviews_by_rating(db, user_id)
    stats_by_type = repo.quiz_stats_by_type(db, user_id)

    return StatsDto(
        streak=StreakDto(current=st.current, longest=st.longest, last_active_date=st.last_active),
        totals=TotalsDto(
            reviews=sum(scheduled for _, scheduled, _ in reviews_by_day),
            # Dùng lại hàm sẵn có của srs thay vì viết lại `count(*) WHERE repetitions >= 1`:
            # hai định nghĩa cho "đã học" sẽ trôi khỏi nhau.
            learned_words=srs_repo.count_learned(db, user_id),
            # Cùng ngưỡng với `mastered` của từng chủ đề. "Đã thuộc" phải có đúng MỘT nghĩa
            # trên toàn hệ thống, nếu không hai ô cạnh nhau ở màn Hôm nay nói ngược nhau.
            mastered_words=srs_repo.count_mastered(db, user_id),
            learning_words=srs_repo.count_learning(db, user_id),
            # Cùng lý do với streak: chỉ đếm ngày có ôn THEO LỊCH.
            active_days=len(scheduled_review_days),
            avg_band=_average_band(repo.count_by_band_level(db, user_id)),
            # `count_introduced_since` đếm số TỪ lần đầu bước vào vòng ôn. Cố ý KHÔNG phải
            # "số từ đạt ngưỡng thuộc trong tuần": `review_log` không lưu `repetitions` nên
            # con số đó không tính được từ dữ liệu đang có, và bịa ra một xấp xỉ rồi gắn nhãn
            # chính xác cho nó còn tệ hơn là không có.
            introduced_last7=srs_repo.count_introduced_since(
                db, user_id, _introduced_window_start(today)
            ),
        ),
        daily=[
            DailyPoint(
                date=day,
                reviews=scheduled_by_day.get(day, 0),
                practice=practice_by_day.get(day, 0),
            )
            for day in _window(today)
        ],
        recall=RecallDto(
            again=counts_by_rating.get("AGAIN", 0),
            hard=counts_by_rating.get("HARD", 0),
            good=counts_by_rating.get("GOOD", 0),
            easy=counts_by_rating.get("EASY", 0),
        ),
        quiz=[_quiz_dto(quiz_type, stats_by_type.get(quiz_type.value)) for quiz_type in QuizType],
    )


def _today() -> date:
    """Hôm nay theo `settings.tz`, KHÔNG theo múi giờ của tiến trình.

    Phải là cùng một múi giờ mà `repository._local_date()` dùng để gom nhóm. Trên Docker
    hai thứ đó trùng nhau vì container nhận biến `TZ`, nhưng trên Vercel tiến trình chạy giờ
    UTC — dùng `datetime.now().astimezone()` ở đó là lệch 7 tiếng, và ô cuối của heatmap trỏ
    sai ngày trong 7 giờ mỗi ngày.
    """
    return datetime.now(ZoneInfo(get_settings().tz)).date()


def _window(today: date) -> list[date]:
    """`WINDOW_DAYS` ngày liên tục kết thúc ở hôm nay, tăng dần."""
    return [today - timedelta(days=WINDOW_DAYS - 1 - i) for i in range(WINDOW_DAYS)]


def _introduced_window_start(today: date) -> datetime:
    """Nửa đêm — THEO `settings.tz` — của ngày mở đầu cửa sổ `introducedLast7`.

    Mốc phải mang offset của `settings.tz` chứ không phải `.astimezone()` (giờ hệ thống) như
    `srs.service._introduced_today`: ở đây "hôm nay" đã được `_today()` tính theo
    `settings.tz`, và trên Vercel tiến trình chạy giờ UTC nên hai múi giờ khác nhau — trộn
    chúng lại là cửa sổ lệch 7 tiếng ở hai đầu.
    Gửi một `datetime` KHÔNG có offset xuống Postgres còn tệ hơn: nó tự diễn giải theo
    timezone của phiên, thứ không kiểm soát được.

    Cùng biên với cách `daily` gom nhóm: `daily` gom theo `(reviewed_at AT TIME ZONE tz)::date`,
    và "ngày địa phương >= hôm nay − 6" tương đương "reviewed_at >= nửa đêm địa phương của
    ngày đó" — một biên duy nhất, viết bằng hai thứ tiếng.
    """
    start_day = today - timedelta(days=INTRODUCED_WINDOW_DAYS - 1)
    return datetime.combine(start_day, time.min, tzinfo=ZoneInfo(get_settings().tz))


def _average_band(counts_by_band: list[tuple[str, int]]) -> float | None:
    """Trung bình có trọng số của những chuỗi band ĐỌC ĐƯỢC. `None` khi không có chuỗi nào.

    Hàng không parse được bị BỎ QUA, không bị coi là 0: một từ Gemini trả "chưa rõ" mà kéo
    trung bình của cả sổ xuống thì con số vẫn trông hợp lý và không ai lần ra được.

    `None` ở đây là "chưa có band nào", khác hẳn `0.0`. Trả 0.0 cho ca đó là bịa ra một phép
    đo.
    """
    total = 0.0
    total_words = 0
    for band_value, count_for_band in counts_by_band:
        band = _parse_band(band_value)
        if band is None:
            continue
        total += band * count_for_band
        total_words += count_for_band
    if total_words == 0:
        return None
    # Một chữ số thập phân: thang IELTS chỉ nhảy 0.5, in thêm chữ số là bịa ra độ chính xác
    # không tồn tại — và làm con số nhảy loạn mỗi lần lưu thêm một từ.
    return round(total / total_words, 1)


def _parse_band(band_value: str) -> float | None:
    """Chuỗi `band_level` → số, hoặc `None` nếu không đọc được."""
    try:
        band = float(band_value)
    except ValueError:
        return None
    # Bắt `ValueError` một mình là CHƯA đủ: `float("nan")` và `float("inf")` chạy êm. Một NaN
    # lọt vào trung bình thì response mang literal `NaN`/`Infinity` — JSON không có hai thứ
    # đó, `JSON.parse` của trình duyệt ném lỗi, và cả màn Hôm nay trắng vì một hàng rác.
    return band if math.isfinite(band) else None


def _quiz_dto(quiz_type: QuizType, row: tuple[int, int, float | None] | None) -> QuizTypeStatsDto:
    """Loại chưa làm lần nào vẫn có hàng với số 0 — vắng hàng thì UI phải phân nhánh "chưa
    làm loại này" ở ba chỗ."""
    if row is None:
        return QuizTypeStatsDto(type=quiz_type, attempts=0, correct=0, avg_score=None)

    attempts, correct, mean_score = row
    reports_score = quiz_type is QuizType.FREE_WRITE and mean_score is not None
    return QuizTypeStatsDto(
        type=quiz_type,
        attempts=attempts,
        correct=correct,
        avg_score=round(mean_score) if reports_score and mean_score is not None else None,
    )
