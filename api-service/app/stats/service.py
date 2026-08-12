"""Ghép ba câu truy vấn và hàm streak thành một `StatsDto`."""

from __future__ import annotations

from datetime import date, datetime, timedelta
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
from app.stats.streak import tinh_streak

#: Độ dài cửa sổ `daily`. 91 = 13 tuần chẵn. Đổi số này là đổi hợp đồng API — mirror
#: TypeScript và test đều dựa vào "đúng 91 phần tử".
WINDOW_DAYS = 91


def lay_thong_ke(db: Session, user_id: int) -> StatsDto:
    theo_ngay = repo.dem_luot_on_theo_ngay(db, user_id)
    hom_nay = _hom_nay()

    # BẪY: `theo_ngay` chứa CẢ những ngày chỉ có lượt luyện thêm (scheduled = 0). Lấy
    # thẳng danh sách ngày từ đó là cho streak tính cả ngày chỉ luyện — phá đúng quy tắc
    # "streak đo kỷ luật theo lịch", mà không ai chạm vào `streak.py`.
    ngay_co_on_theo_lich = [ngay for ngay, scheduled, _ in theo_ngay if scheduled > 0]
    st = tinh_streak(ngay_co_on_theo_lich, hom_nay)

    scheduled_theo_ngay = {ngay: scheduled for ngay, scheduled, _ in theo_ngay}
    practice_theo_ngay = {ngay: practice for ngay, _, practice in theo_ngay}
    theo_rating = repo.dem_luot_on_theo_rating(db, user_id)
    theo_loai = repo.thong_ke_quiz_theo_loai(db, user_id)

    return StatsDto(
        streak=StreakDto(current=st.current, longest=st.longest, last_active_date=st.last_active),
        totals=TotalsDto(
            reviews=sum(scheduled for _, scheduled, _ in theo_ngay),
            # Dùng lại hàm sẵn có của srs thay vì viết lại `count(*) WHERE repetitions >= 1`:
            # hai định nghĩa cho "đã học" sẽ trôi khỏi nhau.
            learned_words=srs_repo.count_learned(db, user_id),
            # Cùng lý do với streak: chỉ đếm ngày có ôn THEO LỊCH.
            active_days=len(ngay_co_on_theo_lich),
        ),
        daily=[
            DailyPoint(
                date=ngay,
                reviews=scheduled_theo_ngay.get(ngay, 0),
                practice=practice_theo_ngay.get(ngay, 0),
            )
            for ngay in _cua_so(hom_nay)
        ],
        recall=RecallDto(
            again=theo_rating.get("AGAIN", 0),
            hard=theo_rating.get("HARD", 0),
            good=theo_rating.get("GOOD", 0),
            easy=theo_rating.get("EASY", 0),
        ),
        quiz=[_quiz_dto(loai, theo_loai.get(loai.value)) for loai in QuizType],
    )


def _hom_nay() -> date:
    """Hôm nay theo `settings.tz`, KHÔNG theo múi giờ của tiến trình.

    Phải là cùng một múi giờ mà `repository._ngay_dia_phuong()` dùng để gom nhóm. Trên Docker
    hai thứ đó trùng nhau vì container nhận biến `TZ`, nhưng trên Vercel tiến trình chạy giờ
    UTC — dùng `datetime.now().astimezone()` ở đó là lệch 7 tiếng, và ô cuối của heatmap trỏ
    sai ngày trong 7 giờ mỗi ngày.
    """
    return datetime.now(ZoneInfo(get_settings().tz)).date()


def _cua_so(hom_nay: date) -> list[date]:
    """`WINDOW_DAYS` ngày liên tục kết thúc ở hôm nay, tăng dần."""
    return [hom_nay - timedelta(days=WINDOW_DAYS - 1 - i) for i in range(WINDOW_DAYS)]


def _quiz_dto(loai: QuizType, hang: tuple[int, int, float | None] | None) -> QuizTypeStatsDto:
    """Loại chưa làm lần nào vẫn có hàng với số 0 — vắng hàng thì UI phải phân nhánh "chưa
    làm loại này" ở ba chỗ."""
    if hang is None:
        return QuizTypeStatsDto(type=loai, attempts=0, correct=0, avg_score=None)

    attempts, correct, diem_tb = hang
    co_diem = loai is QuizType.FREE_WRITE and diem_tb is not None
    return QuizTypeStatsDto(
        type=loai,
        attempts=attempts,
        correct=correct,
        avg_score=round(diem_tb) if co_diem and diem_tb is not None else None,
    )
