"""Truy vấn của context srs. Mọi câu chạm `srs_card` / `review_log` / `srs_distractor`
nằm ở đây.

Chủ sở hữu suy ra qua `vocab_entry.user_id` — `srs_card` KHÔNG có cột `user_id` riêng
(ràng buộc #13). Mọi truy vấn ở đây vì thế phải join tới `vocab_entry`, KỂ CẢ các câu đếm.
Quên một mệnh đề `WHERE user_id = ?` không làm gì đỏ cả, nó chỉ lặng lẽ cho người này đọc
lịch ôn của người kia.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.srs.models import CardState, Rating, ReviewLog, ReviewMode, SrsCard, SrsDistractor
from app.vocabulary.models import VocabEntry


def _count(db: Session, stmt: Select[tuple[int]]) -> int:
    return int(db.execute(stmt).scalar_one())


def card_exists_for_vocab(db: Session, vocab_entry_id: int) -> bool:
    return (
        db.scalars(select(SrsCard.id).where(SrsCard.vocab_entry_id == vocab_entry_id)).first()
        is not None
    )


def insert_card(db: Session, vocab_entry_id: int, due_date: date) -> SrsCard:
    card = SrsCard(
        vocab_entry_id=vocab_entry_id,
        due_date=due_date,
        state=CardState.NEW.value,
    )
    db.add(card)
    db.flush()
    return card


def find_owned_card(db: Session, card_id: int, user_id: int) -> SrsCard | None:
    """Thẻ của CHÍNH user. Trả None cho thẻ người khác — tầng trên biến nó thành 404.

    Tra thẳng theo `(id, user_id)` chứ KHÔNG tra theo id rồi so chủ sở hữu sau: một bước,
    không có khe hở giữa đọc và kiểm.
    """
    return db.scalars(
        select(SrsCard)
        .join(VocabEntry, SrsCard.vocab_entry_id == VocabEntry.id)
        .where(SrsCard.id == card_id, VocabEntry.user_id == user_id)
    ).first()


def find_due_cards(
    db: Session, user_id: int, today: date, limit: int
) -> list[tuple[SrsCard, VocabEntry]]:
    """Thẻ đã đến hạn, kèm luôn từ tương ứng.

    Lấy cả hai entity trong MỘT câu (thay `join fetch` bên JPA): dựng CardDto cần đủ dữ liệu
    vocab, mà nạp lười từng thẻ một là đúng bài toán N+1.
    """
    stmt = (
        select(SrsCard, VocabEntry)
        .join(VocabEntry, SrsCard.vocab_entry_id == VocabEntry.id)
        .where(
            VocabEntry.user_id == user_id,
            SrsCard.state != CardState.NEW.value,
            SrsCard.due_date <= today,
        )
        .order_by(SrsCard.due_date.asc(), SrsCard.id.asc())
        .limit(limit)
    )
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def find_new_cards(db: Session, user_id: int, limit: int) -> list[tuple[SrsCard, VocabEntry]]:
    stmt = (
        select(SrsCard, VocabEntry)
        .join(VocabEntry, SrsCard.vocab_entry_id == VocabEntry.id)
        .where(VocabEntry.user_id == user_id, SrsCard.state == CardState.NEW.value)
        .order_by(VocabEntry.created_at.asc(), SrsCard.id.asc())
        .limit(limit)
    )
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def count_due(db: Session, user_id: int, today: date) -> int:
    return _count(
        db,
        select(func.count())
        .select_from(SrsCard)
        .join(VocabEntry, SrsCard.vocab_entry_id == VocabEntry.id)
        .where(
            VocabEntry.user_id == user_id,
            SrsCard.state != CardState.NEW.value,
            SrsCard.due_date <= today,
        ),
    )


def count_by_state(db: Session, user_id: int, state: CardState) -> int:
    return _count(
        db,
        select(func.count())
        .select_from(SrsCard)
        .join(VocabEntry, SrsCard.vocab_entry_id == VocabEntry.id)
        .where(VocabEntry.user_id == user_id, SrsCard.state == state.value),
    )


def count_learned(db: Session, user_id: int) -> int:
    return _count(
        db,
        select(func.count())
        .select_from(SrsCard)
        .join(VocabEntry, SrsCard.vocab_entry_id == VocabEntry.id)
        .where(VocabEntry.user_id == user_id, SrsCard.repetitions >= 1),
    )


def count_introduced_since(db: Session, user_id: int, since: datetime) -> int:
    """Số thẻ MỚI đã học kể từ mốc thời gian truyền vào.

    `prev_interval = 0` nhận diện chính xác lượt review đầu đời của một thẻ: thẻ mới có
    `interval_days = 0`, còn bấm Lại luôn đặt interval về 1 nên mọi lượt sau đó đều có
    `prev_interval >= 1`. Nhờ vậy không cần bảng đếm riêng.

    Lọc `mode = SCHEDULED` là bắt buộc: hàng luyện chỉ chứa thẻ `repetitions >= 1` nên hôm
    nay không dòng PRACTICE nào có `prev_interval = 0` — nhưng bất biến đó phụ thuộc vào
    định nghĩa hàng luyện, thứ có thể đổi. Một mệnh đề WHERE làm nó không phụ thuộc nữa.
    """
    return _count(
        db,
        select(func.count())
        .select_from(ReviewLog)
        .join(SrsCard, ReviewLog.card_id == SrsCard.id)
        .join(VocabEntry, SrsCard.vocab_entry_id == VocabEntry.id)
        .where(
            VocabEntry.user_id == user_id,
            ReviewLog.reviewed_at >= since,
            ReviewLog.prev_interval == 0,
            ReviewLog.mode == ReviewMode.SCHEDULED.value,
        ),
    )


def insert_review_log(
    db: Session,
    card_id: int,
    rating: Rating,
    prev_interval: int,
    new_interval: int,
    mode: ReviewMode,
) -> None:
    """`mode` BẮT BUỘC, cố ý không có giá trị mặc định.

    Đặt default `SCHEDULED` cho tiện nghĩa là mọi người gọi sau này mặc nhiên ghi lượt ôn
    theo lịch mà không hề chọn — và ghi nhầm loại ở đây không làm gì đỏ. Bắt buộc thì mypy
    ép từng chỗ gọi phải quyết định.
    """
    db.add(
        ReviewLog(
            card_id=card_id,
            rating=rating.value,
            prev_interval=prev_interval,
            new_interval=new_interval,
            mode=mode.value,
        )
    )
    db.flush()


def find_practice_cards(
    db: Session, user_id: int, limit: int
) -> list[tuple[SrsCard, VocabEntry]]:
    """Hàng luyện thêm: mọi từ đã học ít nhất một lượt, xáo ngẫu nhiên.

    `repetitions >= 1` loại thẻ NEW — lượt đầu đời của một thẻ phải đi đường có lịch, nếu
    không nó mắc kẹt ở trạng thái NEW vĩnh viễn.

    KHÔNG loại thẻ đang đến hạn. Luật "mọi từ đã học" giải thích được bằng một câu, còn "mọi
    từ đã học trừ những từ đến hạn hôm nay" thì không — và luyện một thẻ đang đến hạn không
    làm nó biến mất khỏi hàng ôn thật, đúng như nó phải thế.
    """
    stmt = (
        select(SrsCard, VocabEntry)
        .join(VocabEntry, SrsCard.vocab_entry_id == VocabEntry.id)
        .where(VocabEntry.user_id == user_id, SrsCard.repetitions >= 1)
        .order_by(func.random())
        .limit(limit)
    )
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def find_distractor_by_vocab(db: Session, vocab_entry_id: int) -> SrsDistractor | None:
    return db.scalars(
        select(SrsDistractor).where(SrsDistractor.vocab_entry_id == vocab_entry_id)
    ).first()


def find_fresh_distractors(
    db: Session, vocab_entry_ids: Sequence[int], prompt_version: int
) -> list[SrsDistractor]:
    """Chỉ trả bản ghi còn hiệu lực với version prompt hiện hành.

    Lọc `prompt_version` ngay trong truy vấn là cách làm mồi nhử cũ tự biến mất khi tăng
    version prompt, không cần xoá dữ liệu.

    Không lọc `user_id` ở đây là CỐ Ý và an toàn: id truyền vào luôn lấy từ hàng đợi ôn của
    chính user (đã lọc ở `find_due_cards` / `find_new_cards`), không bao giờ từ client.
    """
    if not vocab_entry_ids:
        return []
    return list(
        db.scalars(
            select(SrsDistractor).where(
                SrsDistractor.vocab_entry_id.in_(vocab_entry_ids),
                SrsDistractor.prompt_version == prompt_version,
            )
        ).all()
    )


def find_vocab_entry(db: Session, vocab_entry_id: int) -> VocabEntry | None:
    """Đọc từ để dựng prompt sinh mồi nhử.

    Không lọc `user_id`: hàm này chỉ chạy trong tác vụ nền, với id đến từ hàng đợi ôn của
    chính user hoặc từ chính từ vừa được lưu — không có đường nào cho id client gửi lên đi
    tới đây. Mọi endpoint nhận id từ client dùng `find_owned_card`.
    """
    return db.get(VocabEntry, vocab_entry_id)
