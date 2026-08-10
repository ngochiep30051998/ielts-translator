"""Nghiệp vụ một lượt tra — bản port của `TranslationService`."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.common.gemini import GeminiClient, GeminiTimeout, get_gemini_client
from app.config import Settings, get_settings
from app.quota.guard import consume
from app.translation import detector
from app.translation import repository as repo
from app.translation.cache import build_cache_key, java_trim, utf16_length
from app.translation.models import (
    LookupCache,
    Mode,
    TranslateRequest,
    TranslateResponse,
)
from app.translation.prompts import PromptLoader, get_prompt_loader
from app.translation.schemas import schema_for

#: Giới hạn cứng phía server; content script cũng chặn ở cùng con số (ràng buộc #9 —
#: `TranslationService.MAX_TEXT_LENGTH` và `shared/text.ts`, đổi thì đổi đồng bộ).
MAX_TEXT_LENGTH = 1500


class TranslationService:
    def __init__(
        self,
        gemini: GeminiClient | None = None,
        prompts: PromptLoader | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._gemini = gemini or get_gemini_client()
        self._prompts = prompts or get_prompt_loader()
        self._settings = settings or get_settings()

    def translate(self, db: Session, user_id: int, request: TranslateRequest) -> TranslateResponse:
        text = java_trim(request.text)
        # Đếm theo đơn vị mã UTF-16 để trùng với `string.length` của JavaScript: phía
        # extension chặn bằng con số đó, nên đếm code point ở đây sẽ nhận những đoạn mà
        # client đã từ chối — hai đầu nói hai luật khác nhau.
        if utf16_length(text) > MAX_TEXT_LENGTH:
            raise AppError.of(
                ErrorCode.TEXT_TOO_LONG,
                f"Đoạn bôi đen quá dài (tối đa {MAX_TEXT_LENGTH} ký tự)",
            )

        direction = detector.detect(text)
        mode = Mode.of(text)
        template = self._prompts.load(direction, mode)
        context = request.context_sentence
        source_hash = build_cache_key(
            text=text,
            context=context,
            direction=direction,
            mode=mode,
            model=self._settings.gemini_model,
            prompt_version=template.version,
        )

        cached = repo.find_by_source_hash(db, source_hash)
        if cached is not None:
            repo.increment_hit_count(db, cached.id)
            return TranslateResponse(
                direction=direction, mode=mode, cached=True, payload=cached.response
            )

        # SAU cache, TRƯỚC Gemini: cache hit không chạm Gemini nên không tính hạn mức.
        consume(db, user_id)

        payload = self._gemini.generate_json(
            template.render_text(text, context),
            schema_for(direction, mode),
            GeminiTimeout.TRANSLATE,
        )

        repo.save(
            db,
            LookupCache(
                source_hash=source_hash,
                source_text=text,
                direction=direction.value,
                mode=mode.value,
                model=self._settings.gemini_model,
                prompt_version=template.version,
                response=payload,
                hit_count=0,
            ),
        )
        return TranslateResponse(direction=direction, mode=mode, cached=False, payload=payload)


def get_translation_service() -> TranslationService:
    """Dựng mới theo từng request, KHÔNG `lru_cache`.

    Giữ lại một instance sẽ giữ luôn `GeminiClient` đầu tiên — tức là giữ nguyên connection
    pool cũ sau khi test (hoặc cấu hình) đổi `GEMINI_BASE_URL` và reset cache client. Phần
    đắt đỏ duy nhất là parse prompt, và cái đó đã có bộ nhớ đệm riêng ở `get_prompt_loader`.
    """
    return TranslationService()
