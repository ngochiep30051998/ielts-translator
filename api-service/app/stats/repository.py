"""Truy vấn của màn thống kê — đúng ba câu.

File này CỐ Ý đọc chéo cả ba context (srs, quiz, vocabulary). Đó là việc của một read model
báo cáo, khác `quiz/candidates.py` — file đó phải khoanh vùng vì quiz chỉ chạm dữ liệu SRS ở
đúng một chỗ và chỗ đó cần nhìn thấy bằng mắt.

Chủ sở hữu nằm ở ĐÚNG một cột — `vocab_entry.user_id` (ràng buộc #13). Không bảng nào ở đây
có cột đó, nên cả ba câu đều join về `vocab_entry` rồi lọc. Không được đẻ thêm cột `user_id`
ở `review_log` hay `quiz_attempt` cho tiện.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.config import get_settings
from app.quiz.models import QuizAttempt, QuizItem
from app.srs.models import ReviewLog, SrsCard
from app.vocabulary.models import VocabEntry


def _ngay_dia_phuong() -> ColumnElement[date]:
    """`(reviewed_at AT TIME ZONE :tz)::date` với `:tz = settings.tz`.

    TUYỆT ĐỐI không dùng `cast(ReviewLog.reviewed_at, Date)` trần. `reviewed_at` là TIMESTAMPTZ,
    và Postgres cast trần một TIMESTAMPTZ sang `date` bằng cách quy về timezone của PHIÊN kết
    nối hiện tại — KHÔNG PHẢI UTC cố định như trực giác hay lầm tưởng. Timezone phiên là thứ
    không kiểm soát được: UTC trên Vercel, giá trị biến `TZ` trên Docker, timezone của máy host
    lúc `initdb` trong test bằng `pgserver`. Khi timezone phiên tình cờ trùng `settings.tz` (ví
    dụ máy dev để giờ Việt Nam), cast trần và cast tường minh cho CÙNG kết quả — bug vẫn nằm đó
    nhưng không lộ ra. Chỉ định tường minh bằng `func.timezone(settings.tz, ...)` là cách DUY
    NHẤT đảm bảo kết quả nhất quán bất kể phiên đang chạy ở đâu. Lượt ôn 01:00 sáng giờ Việt Nam
    bị đẩy về ngày hôm trước khi cast trần rơi vào phiên UTC, streak đứt sai, và không có
    exception nào — xem ca `test_luot_on_luc_1h_sang_gio_viet_nam_thuoc_ve_ngay_hom_do` trong
    `test_stats_repository.py` (ca đó tự ép session về UTC bằng `SET LOCAL TIME ZONE 'UTC'` để
    luôn phân biệt được, bất kể máy chạy test đặt giờ gì).
    """
    return cast(func.timezone(get_settings().tz, ReviewLog.reviewed_at), Date)


def dem_luot_on_theo_ngay(db: Session, user_id: int) -> list[tuple[date, int]]:
    """Số lượt ôn mỗi ngày trên TOÀN BỘ lịch sử, tăng dần theo ngày.

    Một câu này nuôi bốn con số: `daily` (service cắt 91 ngày cuối), `totals.reviews` (tổng),
    `totals.activeDays` (số dòng) và `streak`. Tách thành hai câu — một cho cửa sổ 91 ngày,
    một cho streak — là tạo cơ hội cho hai cửa sổ lệch nhau vào lần đầu ai đó sửa hằng số.

    Số dòng trả về bằng số NGÀY đã từng ôn, không phải số lượt: ba năm học đều là ≤1095 dòng.
    """
    ngay = _ngay_dia_phuong().label("ngay")
    cau = (
        select(ngay, func.count().label("so_luot"))
        .select_from(ReviewLog)
        .join(SrsCard, SrsCard.id == ReviewLog.card_id)
        .join(VocabEntry, VocabEntry.id == SrsCard.vocab_entry_id)
        .where(VocabEntry.user_id == user_id)
        .group_by(ngay)
        .order_by(ngay)
    )
    return [(hang[0], int(hang[1])) for hang in db.execute(cau).all()]


def dem_luot_on_theo_rating(db: Session, user_id: int) -> dict[str, int]:
    """Số lượt ôn theo từng mức tự chấm, toàn bộ lịch sử.

    Trả số lượt THÔ, không trả sẵn tỉ lệ nhớ: tỉ lệ là `1 − again/tổng`, một phép chia ở
    client. Trả cả hai là dựng hai nguồn sự thật cho cùng một con số.

    Mức chưa xuất hiện lần nào thì VẮNG khỏi dict — service tự bù 0.
    """
    cau = (
        select(ReviewLog.rating, func.count())
        .select_from(ReviewLog)
        .join(SrsCard, SrsCard.id == ReviewLog.card_id)
        .join(VocabEntry, VocabEntry.id == SrsCard.vocab_entry_id)
        .where(VocabEntry.user_id == user_id)
        .group_by(ReviewLog.rating)
    )
    return {str(hang[0]): int(hang[1]) for hang in db.execute(cau).all()}


def thong_ke_quiz_theo_loai(db: Session, user_id: int) -> dict[str, tuple[int, int, float | None]]:
    """`(số lượt, số lượt đúng, điểm trung bình)` theo từng loại quiz, toàn bộ lịch sử.

    `avg_score` trả nguyên trạng cho MỌI loại. Việc bỏ nó đi với `FILL_BLANK` và
    `COLLOCATION_CHOICE` là quyết định của service — repository chỉ đọc, không diễn giải.

    Loại chưa làm lần nào thì VẮNG khỏi dict; service tự bù hàng 0 để `quiz` luôn đủ 3 phần tử.
    """
    cau = (
        select(
            QuizItem.type,
            func.count(),
            func.count().filter(QuizAttempt.correct),
            func.avg(QuizAttempt.score),
        )
        .select_from(QuizAttempt)
        .join(QuizItem, QuizItem.id == QuizAttempt.quiz_item_id)
        .join(VocabEntry, VocabEntry.id == QuizItem.vocab_entry_id)
        .where(VocabEntry.user_id == user_id)
        .group_by(QuizItem.type)
    )
    return {
        str(hang[0]): (int(hang[1]), int(hang[2]), None if hang[3] is None else float(hang[3]))
        for hang in db.execute(cau).all()
    }
