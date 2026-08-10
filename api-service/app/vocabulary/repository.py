"""Truy vấn của context vocabulary. Mọi câu chạm `vocab_entry` nằm ở đây.

Bản port của `VocabEntryRepository`. Giữ nguyên nguyên tắc gắt nhất của bản Java: hàm nào
đọc dữ liệu học của MỘT người thì nhận `user_id` và nhét nó thẳng vào mệnh đề WHERE. Tra
theo id rồi so chủ sở hữu ở tầng service để lại một khe giữa đọc và kiểm, và một chỗ quên
so là rò dữ liệu im lặng — không có gì đỏ (ràng buộc #13).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.vocabulary.models import VocabEntry


def find_by_user_term_pos(db: Session, user_id: int, term: str, pos: str) -> VocabEntry | None:
    """Tra theo đúng bộ ba của ràng buộc `uq_vocab_user_term_pos (user_id, term, pos)`.

    Lệch một cột so với ràng buộc UNIQUE là kiểm trước một chuyện rồi để database từ chối
    một chuyện khác — tức 500 thay vì `alreadyExists`.
    """
    return db.scalars(
        select(VocabEntry).where(
            VocabEntry.user_id == user_id,
            VocabEntry.term == term,
            VocabEntry.pos == pos,
        )
    ).first()


def find_by_id_and_user(db: Session, entry_id: int, user_id: int) -> VocabEntry | None:
    return db.scalars(
        select(VocabEntry).where(VocabEntry.id == entry_id, VocabEntry.user_id == user_id)
    ).first()


def find_all_by_user_newest_first(db: Session, user_id: int) -> Sequence[VocabEntry]:
    return db.scalars(
        select(VocabEntry)
        .where(VocabEntry.user_id == user_id)
        .order_by(VocabEntry.created_at.desc(), VocabEntry.id.desc())
    ).all()


def find_owned_ids(db: Session, user_id: int, ids: Sequence[int]) -> list[int]:
    """Lọc danh sách id do CLIENT gửi lên xuống còn những id thật sự thuộc về user."""
    if not ids:
        return []
    return list(
        db.scalars(
            select(VocabEntry.id).where(
                VocabEntry.user_id == user_id, VocabEntry.id.in_(list(ids))
            )
        ).all()
    )


def find_all_by_ids(db: Session, ids: Sequence[int]) -> Sequence[VocabEntry]:
    """Nạp nhiều từ theo id, KHÔNG lọc chủ sở hữu — tương đương `findAllById` của JpaRepository.

    Chỉ an toàn khi danh sách id đã đi qua `find_owned_ids` trước đó (đường của
    `/api/quiz/generate`). Gọi thẳng hàm này với id nhận từ client là mở đúng lỗ IDOR mà
    ràng buộc #13 tồn tại để chặn.
    """
    if not ids:
        return []
    return db.scalars(select(VocabEntry).where(VocabEntry.id.in_(list(ids)))).all()


def find_by_id_unscoped(db: Session, entry_id: int) -> VocabEntry | None:
    """Tương đương `findById` của JpaRepository — dùng cho việc nền (sinh distractor) chạy
    trên một id đã được xác thực chủ sở hữu từ trước. Endpoint phục vụ request của người
    dùng phải dùng `find_by_id_and_user`."""
    return db.get(VocabEntry, entry_id)


def _search_conditions(
    user_id: int, q: str | None, tag: str | None
) -> list[ColumnElement[bool]]:
    """Điều kiện dùng chung cho câu lấy dữ liệu VÀ câu đếm.

    Dùng chung là bắt buộc, không phải gọn gàng: bản Java phải chép tay `user_id = :userId`
    vào cả `value` lẫn `countQuery`, và quên ở câu đếm thì danh sách đúng nhưng
    `totalElements` đếm cả sổ từ người khác — phân trang sai và lộ kích thước dữ liệu của họ.
    """
    conditions: list[ColumnElement[bool]] = [VocabEntry.user_id == user_id]
    if q is not None:
        # `%` và `_` trong q vẫn là ký tự đại diện, y như bản Java nối chuỗi `'%' || :q || '%'`.
        pattern = f"%{q}%"
        conditions.append(
            or_(VocabEntry.term.ilike(pattern), VocabEntry.meaning_vi.ilike(pattern))
        )
    if tag is not None:
        # `@>` (mảng chứa phần tử) — khớp index GIN `idx_vocab_tags`.
        conditions.append(VocabEntry.tags.contains([tag]))
    return conditions


def search(
    db: Session, user_id: int, q: str | None, tag: str | None, page: int, size: int
) -> tuple[Sequence[VocabEntry], int]:
    """Một trang sổ từ cùng TỔNG số bản ghi khớp — trả cả hai vì `Page<T>` bên Java trả cả hai."""
    conditions = _search_conditions(user_id, q, tag)

    rows = (
        select(VocabEntry)
        .where(*conditions)
        # Tiêu chí phụ `id DESC` không có trong bản Java và cố ý thêm: bên đó `created_at`
        # do Java gán bằng `Instant.now()` nên hai hàng khó trùng, còn ở đây nó là
        # `DEFAULT now()` của Postgres — tức thời điểm BẮT ĐẦU TRANSACTION, giống hệt nhau
        # cho mọi hàng thêm trong cùng một transaction. Không có tiêu chí phụ thì thứ tự
        # của những hàng đó là tuỳ hứng và phân trang có thể lặp/bỏ sót bản ghi.
        .order_by(VocabEntry.created_at.desc(), VocabEntry.id.desc())
        .offset(page * size)
        .limit(size)
    )
    total = db.scalar(select(func.count()).select_from(VocabEntry).where(*conditions))
    return db.scalars(rows).all(), int(total or 0)


def insert(db: Session, entry: VocabEntry) -> None:
    """Ghi hàng mới và LẤY VỀ id ngay (`flush`), chưa commit.

    Cần id trước khi trả response và trước khi tạo thẻ ôn. Commit vẫn do `get_db` lo khi
    handler trả về bình thường — nên từ và thẻ ôn hoặc cùng có, hoặc cùng không.
    """
    db.add(entry)
    db.flush()


def delete(db: Session, entry: VocabEntry) -> None:
    db.delete(entry)
