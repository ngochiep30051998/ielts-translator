"""POST /api/vocab · GET /api/vocab · GET /api/vocab/export.csv · GET /api/vocab/{id} ·
DELETE /api/vocab/{id}"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Response

from app.auth.deps import CurrentUserId, Db
from app.vocabulary import service
from app.vocabulary.models import (
    SaveVocabRequest,
    SaveVocabResponse,
    VocabEntryDto,
    VocabPage,
)

router = APIRouter(prefix="/api/vocab", tags=["vocabulary"])

#: Trần kích thước trang. Client tự do gửi `size`, nhưng một request `size=100000` là một
#: cách vô tình (hoặc cố ý) kéo cả sổ từ về trong một lượt.
MAX_PAGE_SIZE = 100


@router.post("", response_model=SaveVocabResponse)
def save(
    request: SaveVocabRequest, db: Db, user_id: CurrentUserId, tasks: BackgroundTasks
) -> SaveVocabResponse:
    """`tasks` mang vai trò `@TransactionalEventListener(AFTER_COMMIT)` bên Java: lượt sinh
    mồi nhử được xếp vào đây và chỉ chạy sau khi response đã trả, tức sau khi `get_db` đã
    commit. Gọi thẳng trong handler sẽ làm thao tác lưu treo tới 15 giây chờ Gemini."""
    return service.save(db, user_id, request, tasks)


@router.get("", response_model=VocabPage)
def search(
    db: Db,
    user_id: CurrentUserId,
    q: Annotated[str | None, Query()] = None,
    tag: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1)] = 20,
) -> VocabPage:
    return service.search(db, user_id, q, tag, page, min(size, MAX_PAGE_SIZE))


# PHẢI khai trước `/{id}`: FastAPI so khớp route theo THỨ TỰ khai báo, nên nếu `/{id}` đứng
# trước thì "export.csv" rơi vào nó, không ép được sang int và request chết bằng lỗi validate
# thay vì trả file.
@router.get("/export.csv", response_class=Response)
def export_csv(db: Db, user_id: CurrentUserId) -> Response:
    return Response(
        content=service.export_csv(db, user_id),
        media_type="text/csv; charset=UTF-8",
        headers={"Content-Disposition": 'attachment; filename="vocabulary.csv"'},
    )


@router.get("/{entry_id}", response_model=VocabEntryDto)
def find_by_id(entry_id: int, db: Db, user_id: CurrentUserId) -> VocabEntryDto:
    return service.find_by_id(db, user_id, entry_id)


@router.delete("/{entry_id}", status_code=204)
def delete(entry_id: int, db: Db, user_id: CurrentUserId) -> Response:
    service.delete(db, user_id, entry_id)
    return Response(status_code=204)
