"""GET /api/srs/due · GET /api/srs/stats · POST /api/srs/review"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Response

from app.auth.deps import CurrentUserId, Db
from app.srs import service
from app.srs.models import CardDto, PracticeRequest, ReviewRequest, ReviewResponse, SrsStatsDto

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


@router.get("/practice", response_model=list[CardDto])
def practice_queue(
    user_id: CurrentUserId,
    db: Db,
    tasks: BackgroundTasks,
    limit: int = 50,
) -> list[CardDto]:
    """Xấp thẻ luyện thêm — mọi từ đã học, xáo ngẫu nhiên. Không có khái niệm "đến hạn" ở
    đây, nên cũng không có tham số `newLimit`."""
    return service.practice_queue(db, user_id, _clamp(limit, MAX_LIMIT), tasks)


@router.post("/practice", status_code=204)
def submit_practice(request: PracticeRequest, user_id: CurrentUserId, db: Db) -> Response:
    """Tách hẳn khỏi `POST /review` chứ không thêm field `mode` vào đó.

    `ReviewResponse` mang `nextDueDate`, `intervalDays`, `easeFactor` — luyện thêm không có
    ba thứ đó, nên gộp chung buộc phải trả số giả cho nửa số lượt gọi. Và nhầm mode là hỏng
    im lặng: gửi PRACTICE cho một lượt ôn thật thì lịch đứng yên mãi mãi.
    """
    service.practice(db, user_id, request.card_id, request.rating)
    return Response(status_code=204)


def _clamp(value: int, max_value: int) -> int:
    """limit phải >= 1: một hàng đợi dài 0 phần tử là câu trả lời vô nghĩa cho tab ôn, và
    bên Java `PageRequest.of(0, 0)` ném thẳng IllegalArgument."""
    return max(1, min(value, max_value))
