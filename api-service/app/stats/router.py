"""GET /api/stats"""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.deps import CurrentUserId, Db
from app.stats import service
from app.stats.models import StatsDto

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsDto)
def stats(user_id: CurrentUserId, db: Db) -> StatsDto:
    """Không tham số: cửa sổ thời gian là hằng số phía server (`service.WINDOW_DAYS`).

    Chưa học gì KHÔNG phải lỗi — trả toàn số 0, không bao giờ 404.
    """
    return service.get_stats(db, user_id)
