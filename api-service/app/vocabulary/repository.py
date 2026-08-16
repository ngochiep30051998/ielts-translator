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

<<<<<<< Updated upstream
=======
from app.srs.models import MASTERED_REPETITIONS, SrsCard
>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
=======
def _select_kem_the() -> Select[tuple[VocabEntry, SrsCard]]:
    """`vocab_entry LEFT JOIN srs_card` — nguồn của ba field `srs*` trong `VocabEntryDto`.

    LEFT chứ không INNER, và đây là chỗ dễ đổi nhầm nhất: từ có `pos = 'phrase'` KHÔNG được
    tạo thẻ ôn (`card_creator.tao_the_khi_luu_tu`), nên INNER JOIN sẽ lặng lẽ làm chúng biến
    mất khỏi sổ từ trong khi `totalElements` — đến từ một câu đếm riêng, không join — vẫn
    đếm chúng. Triệu chứng là phân trang lệch, không phải lỗi.

    Không sợ nhân bản hàng: `srs_card.vocab_entry_id` có ràng buộc UNIQUE, nên mỗi từ khớp
    tối đa một thẻ. Nhờ vậy câu đếm KHÔNG cần join theo.

    Kiểu khai là `SrsCard` chứ không `SrsCard | None` vì `Select` không diễn đạt được vế
    phải của LEFT JOIN có thể vắng; người gọi phải tự đón `None` — xem `search`.
    """
    return select(VocabEntry, SrsCard).outerjoin(
        SrsCard, SrsCard.vocab_entry_id == VocabEntry.id
    )


def find_by_id_and_user_with_card(
    db: Session, entry_id: int, user_id: int
) -> tuple[VocabEntry, SrsCard | None] | None:
    """Như `find_by_id_and_user` nhưng kèm thẻ ôn, để dựng `VocabEntryDto` đủ field."""
    hang = db.execute(
        _select_kem_the().where(VocabEntry.id == entry_id, VocabEntry.user_id == user_id)
    ).first()
    return (hang[0], hang[1]) if hang is not None else None


def count_tags(db: Session, user_id: int) -> list[tuple[str, int, int]]:
    """`(tag, số từ mang tag đó, số từ ĐÃ THUỘC trong đó)` của MỘT người, `count DESC, tag ASC`.

    `count(DISTINCT vocab_entry.id)` chứ không `count(*)`: `unnest` bung mảng thành nhiều
    dòng, nên một hàng có `tags = {'x','x'}` (POST không lọc trùng trong mảng client gửi
    lên) sẽ được đếm hai lần. Chip hiện "2 từ" mà bấm vào chỉ ra một — sai ở đúng chỗ người
    dùng đối chiếu được. Con số `mastered` dùng lại y hệt cách đếm đó, vì frontend chia hai
    số cho nhau ra phần trăm: lệch cách đếm là ra tỉ lệ trên 100%.

    Tiêu chí phụ `tag ASC` không phải để đẹp: thiếu nó thì thứ tự các tag cùng số lượng là
    tuỳ hứng và hàng chip nhảy vị trí giữa hai lần tải trang.

    LEFT JOIN `srs_card` (không phải INNER): từ `pos = 'phrase'` không hề có thẻ ôn, và
    INNER JOIN sẽ lặng lẽ vứt chúng khỏi cả `count` — chip chủ đề đếm thiếu đúng những từ
    người dùng không đoán được lý do. Với LEFT JOIN thì `repetitions` là NULL, và
    `NULL >= 5` ra NULL chứ không TRUE nên chúng tự rơi khỏi `mastered`. Không sợ nhân bản
    hàng vì `srs_card.vocab_entry_id` là UNIQUE.

    KHÔNG lọc thêm `state != 'RELEARNING'`: bấm "Lại" đặt `repetitions = 0`
    (`scheduler.next_schedule`), nên thẻ đang học lại không thể đạt ngưỡng — thêm điều kiện
    thứ hai chỉ tạo cơ hội cho nó lệch khỏi luật ở `vocab-progress.ts`.
    """
    # Hai chi tiết của đoạn dựng dưới đây đều đã trả giá một lần:
    #
    # `JOIN LATERAL ... ON true` chứ không để `unnest` đứng rời trong FROM — Postgres hiểu cả
    # hai như nhau (LATERAL là ngầm định với lời gọi hàm), nhưng bộ kiểm tra của SQLAlchemy
    # không thấy được sự phụ thuộc đó và cảnh báo "cartesian product" ở MỖI lượt gọi. Cảnh
    # báo sai vẫn là cảnh báo phải đọc rồi bỏ qua, và thói quen bỏ qua là thứ làm lọt cảnh
    # báo thật.
    #
    # `render_derived` là bắt buộc, không phải trang trí — thiếu nó thì SQLAlchemy sinh
    # `AS tag_bung` trần, Postgres đặt tên cột kết quả theo TÊN HÀM (`unnest`), và câu chạy
    # thẳng vào lỗi "column tag_bung.tag does not exist".
    bung = (
        func.unnest(VocabEntry.tags)
        .table_valued("tag")
        .render_derived(name="tag_bung", with_types=False)
        .lateral()
    )
    so_tu = func.count(distinct(VocabEntry.id))
    so_tu_thuoc = func.count(distinct(VocabEntry.id)).filter(
        SrsCard.repetitions >= MASTERED_REPETITIONS
    )
    stmt = (
        select(bung.c.tag, so_tu, so_tu_thuoc)
        .select_from(VocabEntry)
        .outerjoin(SrsCard, SrsCard.vocab_entry_id == VocabEntry.id)
        .join(bung, true())
        .where(VocabEntry.user_id == user_id)
        .group_by(bung.c.tag)
        .order_by(so_tu.desc(), bung.c.tag.asc())
    )
    return [
        (str(hang[0]), int(hang[1]), int(hang[2])) for hang in db.execute(stmt).all()
    ]


def _untagged_condition() -> ColumnElement[bool]:
    """"Từ này chưa gắn thẻ nào" — cùng một điều kiện cho bộ lọc lẫn câu đếm.

    `cardinality(tags) = 0` chứ không `coalesce(cardinality(tags), 0) = 0`: mảng RỖNG mới là
    "chưa gắn thẻ", còn NULL sẽ là "không biết". Cột đang `NOT NULL DEFAULT '{}'` (V2) nên
    hai cách hôm nay cho cùng kết quả — viết dạng an toàn để một lần nới `NOT NULL` về sau
    không lặng lẽ kéo theo cả những hàng chưa xác định vào chip "Chưa gắn".
    """
    return func.cardinality(VocabEntry.tags) == 0


def count_total_and_untagged(db: Session, user_id: int) -> tuple[int, int]:
    """`(tổng số từ, số từ chưa gắn thẻ)` của MỘT người — hai con số trong MỘT câu.

    Một câu chứ không hai: hai câu đọc hai ảnh chụp khác nhau của cùng một bảng, nên một
    lượt xoá từ chen vào giữa cho ra `untagged > total`. Con số đó không sai đủ để ai nghi
    ngờ, chỉ đủ để hàng chip cộng lại không khớp.
    """
    hang = db.execute(
        select(func.count(), func.count().filter(_untagged_condition()))
        .select_from(VocabEntry)
        .where(VocabEntry.user_id == user_id)
    ).one()
    return int(hang[0]), int(hang[1])


>>>>>>> Stashed changes
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
