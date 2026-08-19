"""Truy vấn của context quiz. Mọi câu chạm `quiz_item` / `quiz_attempt` nằm ở đây.

Có ĐÚNG MỘT ngoại lệ và nó cố ý: câu chọn ứng viên (đọc `srs_card`) nằm ở `candidates.py`,
vì đó là ACL sang context srs chứ không phải truy vấn của quiz. Tách ra để chỗ duy nhất
quiz chạm dữ liệu SRS nhìn thấy được bằng mắt.

Chủ sở hữu nằm ở ĐÚNG một cột — `vocab_entry.user_id` — nên mọi câu ở đây đều join qua
`vocab_entry` để lọc. `quiz_item` treo vào `vocab_entry_id`, `quiz_attempt` treo vào
`quiz_item_id`; không có cột `user_id` nào để nhân bản, và cũng không được đẻ ra.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.quiz.models import QuizAttempt, QuizItem, QuizType
from app.vocabulary.models import VocabEntry


def find_owned_entries_in_order(
    db: Session, user_id: int, vocab_ids: Sequence[int]
) -> list[VocabEntry]:
    """Từ trong sổ của CHÍNH user, theo đúng thứ tự người gọi yêu cầu.

    Id lạ hoặc id của người khác bị bỏ qua chứ không thành lỗi — đó là hợp đồng của
    `POST /api/quiz/generate`: gửi id không tồn tại thì đề chỉ vắng câu đó.

    Bản Java tách làm hai bước (`VocabService.filterOwnedIds` rồi `findAllById` không lọc
    user). Gộp lại một câu ở đây cho cùng kết quả nhưng bỏ được đường đi trong đó một
    `findAllById` trần đứng cạnh dữ liệu của mọi người.
    """
    if not vocab_ids:
        return []
    found = {
        entry.id: entry
        for entry in db.scalars(
            select(VocabEntry).where(VocabEntry.user_id == user_id, VocabEntry.id.in_(vocab_ids))
        )
    }
    ordered: list[VocabEntry] = []
    seen: set[int] = set()
    for vocab_id in vocab_ids:
        entry = found.get(vocab_id)
        if entry is not None and vocab_id not in seen:
            seen.add(vocab_id)
            ordered.append(entry)
    return ordered


def find_reusable(
    db: Session,
    user_id: int,
    vocab_ids: Sequence[int],
    types: Sequence[QuizType],
    prompt_version: int,
) -> list[QuizItem]:
    """Đề còn tái dùng được: đúng từ, đúng loại đang hỏi, `prompt_version` còn hiệu lực, và
    CHƯA từng có lượt làm nào. Đây là cách hiện thực "không gọi Gemini mỗi lần mở màn quiz".

    Bốn điều kiện đều bắt buộc và mỗi cái hỏng theo một kiểu riêng: bỏ điều kiện user là rò
    đề của người khác; bỏ `prompt_version` là sửa prompt xong đề cũ vẫn sống mãi; bỏ "chưa có
    lượt làm" là câu vừa làm xong hiện lại ở đề sau.

    Không cần `join fetch` như bản JPA: `vocab_entry_id` là cột thẳng trên `quiz_item`, và
    người gọi đã cầm sẵn các `VocabEntry` — không có lazy-load nào để mà N+1.
    """
    if not vocab_ids or not types:
        return []
    has_attempt = select(QuizAttempt.id).where(QuizAttempt.quiz_item_id == QuizItem.id).exists()
    stmt = (
        select(QuizItem)
        .join(VocabEntry, VocabEntry.id == QuizItem.vocab_entry_id)
        .where(
            VocabEntry.user_id == user_id,
            QuizItem.vocab_entry_id.in_(vocab_ids),
            QuizItem.type.in_([quiz_type.value for quiz_type in types]),
            QuizItem.prompt_version == prompt_version,
            ~has_attempt,
        )
        .order_by(QuizItem.id.asc())
    )
    return list(db.scalars(stmt))


def find_owned_item(
    db: Session, quiz_item_id: int, user_id: int
) -> tuple[QuizItem, VocabEntry] | None:
    """Câu hỏi của CHÍNH user, kèm từ gốc. None cho câu của người khác → 404 ở tầng trên.

    Trả 404 chứ KHÔNG 403: 403 xác nhận id đó có tồn tại.

    Trả kèm `VocabEntry` vì mọi người gọi đều cần nó ngay sau đó (dựng DTO, dựng prompt) —
    tách làm hai lượt tra chỉ tạo cơ hội cho lượt thứ hai quên lọc user.
    """
    row = db.execute(
        select(QuizItem, VocabEntry)
        .join(VocabEntry, VocabEntry.id == QuizItem.vocab_entry_id)
        .where(QuizItem.id == quiz_item_id, VocabEntry.user_id == user_id)
    ).first()
    if row is None:
        return None
    return row[0], row[1]


def find_latest_attempt(db: Session, quiz_item_id: int, user_id: int) -> QuizAttempt | None:
    """Lượt làm gần nhất của một câu.

    Sắp theo `id` giảm dần chứ KHÔNG theo `created_at`: cột đó mặc định `now()`, mà `now()`
    trong Postgres là thời điểm bắt đầu transaction — hai lượt trong cùng một transaction sẽ
    trùng mốc thời gian và thứ tự thành ngẫu nhiên. `id` là BIGSERIAL nên luôn tăng.

    Vẫn lọc `user_id` dù người gọi thường đã kiểm quyền sở hữu trước: điều kiện an toàn nằm
    trong CÂU TRUY VẤN thì không phụ thuộc vào thứ tự gọi của tầng trên.
    """
    return db.scalars(
        select(QuizAttempt)
        .join(QuizItem, QuizItem.id == QuizAttempt.quiz_item_id)
        .join(VocabEntry, VocabEntry.id == QuizItem.vocab_entry_id)
        .where(QuizAttempt.quiz_item_id == quiz_item_id, VocabEntry.user_id == user_id)
        .order_by(QuizAttempt.id.desc())
        .limit(1)
    ).first()


def save_item(db: Session, item: QuizItem) -> QuizItem:
    """`flush` chứ không đợi commit: người gọi cần `id` sinh ra để dựng `QuizItemDto`."""
    db.add(item)
    db.flush()
    return item


def save_attempt(db: Session, attempt: QuizAttempt) -> QuizAttempt:
    """Thêm dòng mới mỗi lượt, KHÔNG ghi đè: `quiz_attempt` là lịch sử, và số lượt làm chính
    là tiêu chí xếp ưu tiên ứng viên cho lần sinh đề sau."""
    db.add(attempt)
    db.flush()
    return attempt
