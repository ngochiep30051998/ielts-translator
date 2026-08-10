"""POST /api/translate"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUserId, Db
from app.translation.models import TranslateRequest, TranslateResponse
from app.translation.service import TranslationService, get_translation_service

router = APIRouter(prefix="/api/translate", tags=["translation"])


@router.post("", response_model=TranslateResponse)
def translate(
    request: TranslateRequest,
    user_id: CurrentUserId,
    db: Db,
    service: Annotated[TranslationService, Depends(get_translation_service)],
) -> TranslateResponse:
    return service.translate(db, user_id, request)
