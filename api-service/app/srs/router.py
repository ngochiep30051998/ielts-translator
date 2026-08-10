"""GET /api/srs/due · GET /api/srs/stats · POST /api/srs/review"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query

from app.auth.deps import CurrentUserId, Db
from app.srs import service
from app.srs.models import CardDto, ReviewRequest, ReviewResponse, SrsStatsDto

router = APIRouter(prefix="/api/srs", tags=["srs"])

MAX_LIMIT = 200


@router.get("/due", response_model=list[CardDto])
def due(
    user_id: CurrentUserId,
    db: Db,
    tasks: BackgroundTasks,
    limit: int = 50,
    # alias camelCase là BẮT BUỘC: hợp đồng cũ của Spring lấy tên tham số từ bytecode nên
    # query string là `newLimit`. Để FastAPI tự suy ra `new_limit` thì extension gửi
    # `newLimit` sẽ rơi về mặc định 30 — không lỗi, không test nào đỏ, chỉ là hạn mức từ mới
    # của người dùng bị bỏ qua.
    new_limit: Annotated[int, Query(alias="newLimit")] = 30,
) -> list[CardDto]:
    return service.due(db, user_id, _clamp(limit, MAX_LIMIT), max(0, new_limit), tasks)


@router.get("/stats", response_model=SrsStatsDto)
def stats(
    user_id: CurrentUserId,
    db: Db,
    new_limit: Annotated[int, Query(alias="newLimit")] = 30,
) -> SrsStatsDto:
    return service.stats(db, user_id, max(0, new_limit))


@router.post("/review", response_model=ReviewResponse)
def submit_review(request: ReviewRequest, user_id: CurrentUserId, db: Db) -> ReviewResponse:
    return service.review(db, user_id, request.card_id, request.rating)


def _clamp(value: int, max_value: int) -> int:
    """limit phải >= 1: một hàng đợi dài 0 phần tử là câu trả lời vô nghĩa cho tab ôn, và
    bên Java `PageRequest.of(0, 0)` ném thẳng IllegalArgument."""
    return max(1, min(value, max_value))
