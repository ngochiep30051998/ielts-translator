"""Nghiệp vụ sổ từ — bản port của `VocabService`.

Một khác biệt cố ý so với bản Java: bên đó, việc chạy tiếp sau khi lưu từ mới đi qua
`ApplicationEventPublisher` + `VocabEntrySavedEvent` để module vocabulary không phải biết
module srs tồn tại. Ở đây gọi thẳng hai người nghe của sự kiện đó.

Lý do: `@EventListener` của Spring chạy ĐỒNG BỘ, trong cùng transaction, đúng bằng một lời
gọi hàm — nên lớp gián tiếp kia không mua được tính bất đồng bộ, không mua được khả năng
hỏng độc lập, chỉ mua được việc giấu đi một cạnh phụ thuộc. Với đúng MỘT sự kiện, cái giá
là: đọc code không thấy được điều gì xảy ra sau khi lưu, và gỡ lỗi "sao từ này không có
thẻ ôn" phải đi tìm người nghe trong cả codebase.

`VocabEntrySavedEvent` bên Java có ĐÚNG HAI người nghe, và cả hai phải có mặt ở đây:

* `SrsCardCreator` — `@EventListener` thường, tức đồng bộ trong cùng transaction
  → `tao_the_khi_luu_tu(db, entry)`;
* `DistractorGenerator` — `@TransactionalEventListener(AFTER_COMMIT)` + `@Async`, tức chạy
  sau khi commit và không ai đứng chờ → `distractors.schedule(tasks, id)`, vì
  `BackgroundTasks` của FastAPI chạy sau khi dependency `get_db` đã commit và response đã
  gửi đi.

Bỏ sót người nghe thứ hai không làm gì đỏ: từ vẫn lưu, thẻ ôn vẫn có, chỉ là mồi nhử không
bao giờ được sinh trước — người học phải chờ Gemini ngay giữa lượt ôn đầu tiên.
"""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.srs import distractors
from app.srs.card_creator import tao_the_khi_luu_tu
from app.srs.models import CardState, SrsCard
from app.vocabulary import repository
from app.vocabulary.csv_export import to_csv
from app.vocabulary.models import (
    SaveVocabRequest,
    SaveVocabResponse,
    VocabEntry,
    VocabEntryDto,
    VocabPage,
    VocabTagDto,
    VocabTagsResponse,
    VocabUpdateRequest,
)


def save(
    db: Session, user_id: int, request: SaveVocabRequest, tasks: BackgroundTasks
) -> SaveVocabResponse:
    """Lưu từ mới. Nếu (term, pos) đã có thì KHÔNG ghi đè nội dung cũ — chỉ gộp thêm tag mới —
    và báo `alreadyExists` để UI hiện "Đã có trong sổ"."""
    pos = request.pos if request.pos is not None else ""

    existing = repository.find_by_user_term_pos(db, user_id, request.term, pos)
    if existing is not None:
        _merge_tags(existing, request.tags)
        return SaveVocabResponse(id=existing.id, already_exists=True)

    entry = VocabEntry(
        user_id=user_id,
        term=request.term,
        lemma=request.lemma,
        lang=request.lang,
        pos=pos,
        ipa=request.ipa,
        meaning_vi=request.meaning_vi,
        definition_en=request.definition_en,
        cefr=request.cefr,
        band_level=request.band_level,
        tags=list(request.tags) if request.tags is not None else [],
        source_url=request.source_url,
        source_sentence=request.source_sentence,
        collocations=request.collocations if request.collocations is not None else [],
        examples=request.examples if request.examples is not None else [],
    )
    repository.insert(db, entry)

    # Chỉ chạy ở nhánh lưu MỚI, y như bản Java chỉ phát `VocabEntrySavedEvent` ở đây. Nhánh
    # alreadyExists đã return sớm ở trên, nên không có chuyện lưu lại một từ cũ mà lịch ôn
    # của nó bị đặt lại từ đầu, cũng không có chuyện tốn thêm một lượt gọi Gemini.
    tao_the_khi_luu_tu(db, entry)

    # `schedule` tự commit trước khi xếp tác vụ — đó là phần "AFTER_COMMIT" của bản Java và
    # lý do nó phải nhận `db`. Chi tiết của FastAPI dễ hiểu sai nằm ở đây: `BackgroundTasks`
    # chạy bên trong `await response(...)`, mà lời gọi đó nằm TRONG cùng AsyncExitStack
    # đăng ký các dependency có `yield` — nên tác vụ nền chạy TRƯỚC đoạn sau `yield` của
    # `get_db`, tức trước commit. Tác vụ nền mở session riêng, và một session riêng không
    # nhìn thấy hàng chưa commit: hàm thoát êm, không lỗi, không log, không test nào đỏ —
    # mồi nhử đơn giản là không bao giờ được sinh.
    #
    # Gọi SAU `tao_the_khi_luu_tu` để giữ nguyên bất biến "từ và thẻ ôn hoặc cùng có, hoặc
    # cùng không": commit gói cả hai. `get_db` vẫn commit lần nữa khi handler trả về — một
    # commit rỗng.
    #
    # Không lọc pos ở đây: bản Java cũng phát sự kiện cho mọi từ mới và để chính
    # DistractorGenerator bỏ qua `pos == "phrase"`. Nhân đôi điều kiện ra hai chỗ là để hai
    # chỗ đó lệch nhau về sau.
    distractors.schedule(tasks, db, entry.id)
    return SaveVocabResponse(id=entry.id, already_exists=False)


def _merge_tags(entry: VocabEntry, incoming: list[str] | None) -> None:
    """Gộp tag mới vào tag cũ, giữ thứ tự xuất hiện và bỏ trùng (`LinkedHashSet` bên Java).

    Phải GÁN LẠI `entry.tags` chứ không sửa list tại chỗ: SQLAlchemy theo dõi thay đổi của
    cột mảng qua phép gán, sửa tại chỗ thì UPDATE không bao giờ được sinh ra.
    """
    if not incoming:
        return
    entry.tags = list(dict.fromkeys([*entry.tags, *incoming]))


def search(
    db: Session,
    user_id: int,
    q: str | None,
    tag: str | None,
    untagged: bool,
    page: int,
    size: int,
) -> VocabPage:
    normalised_q = q if q is not None and q.strip() else None
    normalised_tag = tag if tag is not None and tag.strip() else None

    rows, total = repository.search(
        db, user_id, normalised_q, normalised_tag, untagged, page, size
    )
    content = [_to_dto(entry, card) for entry, card in rows]
    # Trần ở 1 để một sổ từ rỗng vẫn có 0 trang chứ không phải "0 phần tử, 1 trang"; đây là
    # cách Spring Data tính, và side panel hiển thị "trang x/y" thẳng từ con số này.
    total_pages = (total + size - 1) // size if size > 0 else 0
    return VocabPage(
        content=content,
        total_elements=total,
        total_pages=total_pages,
        number=page,
        size=size,
        number_of_elements=len(content),
        first=page == 0,
        last=page + 1 >= total_pages,
        empty=not content,
    )


def find_by_id(db: Session, user_id: int, entry_id: int) -> VocabEntryDto:
    """Tra thẳng theo (id, user_id) chứ KHÔNG tra theo id rồi so chủ sở hữu sau — một bước,
    không có khe hở giữa đọc và kiểm.

    Trả NOT_FOUND chứ không FORBIDDEN khi từ thuộc về người khác: FORBIDDEN xác nhận "id này
    có tồn tại", tức là một kênh dò id.
    """
    hang = repository.find_by_id_and_user_with_card(db, entry_id, user_id)
    if hang is None:
        raise AppError.of(ErrorCode.NOT_FOUND, f"Không tìm thấy từ id={entry_id}")
    return _to_dto(*hang)


def update(
    db: Session, user_id: int, entry_id: int, request: VocabUpdateRequest
) -> VocabEntryDto:
    """Sửa một mục sổ từ. Chỉ đụng tới field CÓ MẶT trong body (xem `VocabUpdateRequest`).

    Ngữ nghĩa `tags` ở đây THAY THẾ toàn bộ, ngược với `save()` (gộp thêm qua `_merge_tags`).
    Cố ý tách: gộp là đúng cho lượt bôi đen lưu lại một từ cũ, còn thay thế là đúng cho lượt
    người dùng bấm Sửa — trộn hai ngữ nghĩa vào một đường thì không còn cách nào gỡ một thẻ
    đã gắn nhầm.

    Tra theo `(id, user_id)` trong MỘT bước và trả NOT_FOUND khi không khớp — 403 xác nhận
    id đó tồn tại, tức một kênh dò id (ràng buộc #13).
    """
    hang = repository.find_by_id_and_user_with_card(db, entry_id, user_id)
    if hang is None:
        raise AppError.of(ErrorCode.NOT_FOUND, f"Không tìm thấy từ id={entry_id}")

    entry, card = hang
    # Vế `is not None` thứ hai là để mypy thu hẹp kiểu, không phải điều kiện nghiệp vụ thứ
    # hai — `co_gui` đã bao hàm nó rồi.
    if request.co_gui("meaning_vi") and request.meaning_vi is not None:
        entry.meaning_vi = request.meaning_vi.strip()
    if request.co_gui("tags") and request.tags is not None:
        # GÁN LẠI chứ không sửa list tại chỗ — cùng lý do như `_merge_tags`: SQLAlchemy theo
        # dõi cột mảng qua phép gán. Bỏ thẻ rỗng và thẻ trùng vì cả hai đều lọt được từ ô
        # nhập tự do, và mỗi cái đẻ ra một chip vô nghĩa ở `GET /api/vocab/tags`.
        entry.tags = list(dict.fromkeys(t.strip() for t in request.tags if t.strip()))

    db.flush()
    return _to_dto(entry, card)


def list_tags(db: Session, user_id: int) -> VocabTagsResponse:
    total, untagged = repository.count_total_and_untagged(db, user_id)
    return VocabTagsResponse(
        total=total,
        untagged=untagged,
        tags=[
            VocabTagDto(tag=tag, count=count)
            for tag, count in repository.count_tags(db, user_id)
        ],
    )


def delete(db: Session, user_id: int, entry_id: int) -> None:
    entry = repository.find_by_id_and_user(db, entry_id, user_id)
    if entry is None:
        raise AppError.of(ErrorCode.NOT_FOUND, f"Không tìm thấy từ id={entry_id}")
    repository.delete(db, entry)


def export_csv(db: Session, user_id: int) -> str:
    return to_csv(repository.find_all_by_user_newest_first(db, user_id))


def filter_owned_ids(db: Session, user_id: int, ids: list[int] | None) -> list[int]:
    """Lọc id client gửi lên xuống còn id thuộc về user. Dùng cho `/api/quiz/generate`."""
    if not ids:
        return []
    return repository.find_owned_ids(db, user_id, ids)


def _to_dto(entry: VocabEntry, card: SrsCard | None) -> VocabEntryDto:
    """`card is None` → cả ba field `srs*` giữ nguyên `None`, tức "từ này chưa có thẻ ôn".

    Bù riêng ba field thay vì gắn `relationship` vào `VocabEntry`: quan hệ ORM sẽ nạp lười
    từng thẻ một khi dựng DTO cho cả trang — đúng bài toán N+1 — và `search` đã lấy sẵn thẻ
    trong cùng một câu.
    """
    dto = VocabEntryDto.model_validate(entry)
    if card is None:
        return dto
    return dto.model_copy(
        update={
            "srs_state": CardState(card.state),
            "srs_due_date": card.due_date,
            "srs_repetitions": card.repetitions,
        }
    )
