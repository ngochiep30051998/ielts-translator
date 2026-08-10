"""POST /api/quiz/generate · POST /api/quiz/answer · POST /api/quiz/explain"""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.deps import CurrentUserId, Db
from app.quiz import service
from app.quiz.models import (
    AnswerQuizRequest,
    AnswerResultDto,
    ExplainQuizRequest,
    ExplanationDto,
    GenerateQuizRequest,
    QuizItemDto,
)

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.post("/generate", response_model=list[QuizItemDto])
def generate(request: GenerateQuizRequest, user_id: CurrentUserId, db: Db) -> list[QuizItemDto]:
    return service.generate(db, user_id, request)


@router.post("/answer", response_model=AnswerResultDto)
def answer(request: AnswerQuizRequest, user_id: CurrentUserId, db: Db) -> AnswerResultDto:
    return service.answer(db, user_id, request.quiz_item_id, request.answer)


@router.post("/explain", response_model=ExplanationDto)
def explain(request: ExplainQuizRequest, user_id: CurrentUserId, db: Db) -> ExplanationDto:
    """Giải thích một câu ĐÃ trả lời. Response chứa đáp án, nên endpoint chỉ phục vụ item đã
    có lượt làm — chốt chặn đó nằm trong `explain.py`, không ở đây."""
    return service.explain(db, user_id, request.quiz_item_id)
