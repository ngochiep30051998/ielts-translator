"""Truy vấn của màn thống kê — đúng bốn câu.

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
from app.srs.models import ReviewLog, ReviewMode, SrsCard
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


def dem_luot_on_theo_ngay(db: Session, user_id: int) -> list[tuple[date, int, int]]:
    """`(ngày, số lượt SCHEDULED, số lượt PRACTICE)` trên TOÀN BỘ lịch sử, tăng dần.

    CẢNH BÁO cho người gọi: ngày CHỈ có lượt PRACTICE vẫn nằm trong kết quả, với
    `scheduled = 0`. Đó là hành vi đúng của hàm này — nhưng `streak` và `totals.activeDays`
    PHẢI lọc `scheduled > 0`, nếu không chúng bắt đầu tính cả ngày chỉ luyện thêm. Xem
    docstring của `service.lay_thong_ke`.
    """
    ngay = _ngay_dia_phuong().label("ngay")
    cau = (
        select(
            ngay,
            func.count().filter(ReviewLog.mode == ReviewMode.SCHEDULED.value),
            func.count().filter(ReviewLog.mode == ReviewMode.PRACTICE.value),
        )
        .select_from(ReviewLog)
        .join(SrsCard, SrsCard.id == ReviewLog.card_id)
        .join(VocabEntry, VocabEntry.id == SrsCard.vocab_entry_id)
        .where(VocabEntry.user_id == user_id)
        .group_by(ngay)
        .order_by(ngay)
    )
    return [(hang[0], int(hang[1]), int(hang[2])) for hang in db.execute(cau).all()]


def dem_luot_on_theo_rating(db: Session, user_id: int) -> dict[str, int]:
    """Số lượt ôn theo từng mức tự chấm, toàn bộ lịch sử.

    Trả số lượt THÔ, không trả sẵn tỉ lệ nhớ: tỉ lệ là `1 − again/tổng`, một phép chia ở
    client. Trả cả hai là dựng hai nguồn sự thật cho cùng một con số.

    Chỉ đếm lượt theo lịch — tỉ lệ nhớ trộn hai loại hoạt động thì không so sánh được với
    chính nó tháng trước.

    Mức chưa xuất hiện lần nào thì VẮNG khỏi dict — service tự bù 0.
    """
    cau = (
        select(ReviewLog.rating, func.count())
        .select_from(ReviewLog)
        .join(SrsCard, SrsCard.id == ReviewLog.card_id)
        .join(VocabEntry, VocabEntry.id == SrsCard.vocab_entry_id)
        .where(
            VocabEntry.user_id == user_id,
            ReviewLog.mode == ReviewMode.SCHEDULED.value,
        )
        .group_by(ReviewLog.rating)
    )
    return {str(hang[0]): int(hang[1]) for hang in db.execute(cau).all()}


def dem_band_level(db: Session, user_id: int) -> list[tuple[str, int]]:
    """`(chuỗi band_level, số từ mang đúng chuỗi đó)` của MỘT người. CHƯA parse, chưa lọc rác.

    Trả chuỗi THÔ và để service parse, cố ý:

    * `band_level` là `varchar(8)` do Gemini điền, nên "chưa rõ" hay "6.5-7" là dữ liệu có
      thật. `avg(band_level::numeric)` sẽ làm CẢ câu nổ vì đúng một hàng như vậy — tức tab
      thống kê chết hẳn thay vì bỏ qua một dòng.
    * Lọc rác bằng regex trong SQL thì luật "thế nào là band đọc được" nằm ở hai chỗ (regex
      và Python), và chúng sẽ lệch nhau.

    GROUP BY thay vì trả từng hàng: band chỉ có vài giá trị phân biệt, nên kết quả gọn bất
    kể sổ từ to cỡ nào. Hàng `band_level IS NULL` bị loại ngay tại đây — "chưa có band" không
    phải một giá trị cần parse.
    """
    cau = (
        select(VocabEntry.band_level, func.count())
        .select_from(VocabEntry)
        .where(VocabEntry.user_id == user_id, VocabEntry.band_level.is_not(None))
        .group_by(VocabEntry.band_level)
    )
    return [(str(hang[0]), int(hang[1])) for hang in db.execute(cau).all()]


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
