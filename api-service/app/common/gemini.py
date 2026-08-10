"""Client gọi Gemini với structured output — bản port của `GeminiClient` + `GeminiConfig`.

Ba mức timeout vì độ dài output khác nhau một bậc: dịch một từ trả vài trăm token, sinh
một lô 10 câu quiz trả vài nghìn. Dùng chung 15 giây thì hoặc là sinh quiz đứt giữa chừng,
hoặc là một lượt dịch hỏng bắt người dùng đợi 30 giây mới thấy lỗi.
"""

from __future__ import annotations

import enum
import json
import logging
import time
from functools import lru_cache
from typing import Any

import httpx

from app.common.errors import AppError, ErrorCode
from app.config import Settings, get_settings

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 2

#: Bắt tay TCP không phụ thuộc độ dài output nên dùng chung cho cả ba mức.
CONNECT_TIMEOUT_SECONDS = 5.0


class GeminiTimeout(enum.StrEnum):
    TRANSLATE = "TRANSLATE"
    QUIZ_GENERATE = "QUIZ_GENERATE"
    QUIZ_GRADE = "QUIZ_GRADE"


def _read_timeout(settings: Settings, tier: GeminiTimeout) -> int:
    match tier:
        case GeminiTimeout.TRANSLATE:
            return settings.gemini_timeout_seconds
        case GeminiTimeout.QUIZ_GENERATE:
            return settings.gemini_quiz_generate_timeout_seconds
        case GeminiTimeout.QUIZ_GRADE:
            return settings.gemini_quiz_grade_timeout_seconds
    raise AssertionError(f"GeminiTimeout chưa xử lý: {tier}")  # pragma: no cover


class GeminiClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # Một client cho mỗi mức timeout, dựng sẵn để tái dùng kết nối. Bên Java phải có ba
        # RestClient vì read-timeout nướng vào request factory; ở httpx thì truyền được
        # timeout theo từng request, nhưng giữ ba client vẫn đúng hơn: connection pool
        # riêng theo mức việc, và mã lỗi cấu hình sai không lẫn giữa các mức.
        self._clients: dict[GeminiTimeout, httpx.Client] = {}

    def _client(self, tier: GeminiTimeout) -> httpx.Client:
        existing = self._clients.get(tier)
        if existing is not None:
            return existing
        client = httpx.Client(
            base_url=self._settings.gemini_base_url,
            timeout=httpx.Timeout(
                connect=CONNECT_TIMEOUT_SECONDS,
                read=float(_read_timeout(self._settings, tier)),
                write=CONNECT_TIMEOUT_SECONDS,
                pool=CONNECT_TIMEOUT_SECONDS,
            ),
        )
        self._clients[tier] = client
        return client

    def generate_json(
        self, prompt: str, response_schema: dict[str, Any], tier: GeminiTimeout
    ) -> Any:
        """Gọi Gemini với structured output ở mức timeout `tier`. Chỉ retry lỗi tạm thời
        (5xx, timeout, JSON hỏng) đúng 1 lần. Lỗi quota không retry.

        CỐ Ý không có giá trị mặc định cho `tier`: mặc định cho phép một call sinh quiz lỡ
        tay chạy ở mức 15 giây — không có gì đỏ, test xanh, chỉ hỏng trên máy người dùng
        khi Gemini chậm thật.
        """
        last: AppError | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self._call_once(prompt, response_schema, tier)
            except AppError as ex:
                # Chỉ retry lỗi tạm thời (server tạm ngưng, JSON hỏng do model trả sai định
                # dạng). Liệt kê "được retry" thay vì "không được retry" để an toàn hơn khi
                # sau này thêm ErrorCode mới — mặc định không retry trừ khi biết chắc là
                # tạm thời.
                transient = ex.code in (ErrorCode.GEMINI_UNAVAILABLE, ErrorCode.PARSE_ERROR)
                if not transient:
                    raise
                last = ex
                log.warning(
                    "Gemini lần %d thất bại (%s), %s",
                    attempt,
                    ex.code.value,
                    "thử lại" if attempt < MAX_ATTEMPTS else "bỏ cuộc",
                )
                if attempt < MAX_ATTEMPTS:
                    time.sleep(self._settings.gemini_retry_backoff_millis / 1000)
        assert last is not None  # vòng lặp chạy ít nhất một lần
        raise last

    def _call_once(
        self, prompt: str, response_schema: dict[str, Any], tier: GeminiTimeout
    ) -> Any:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            },
        }
        try:
            response = self._client(tier).post(
                f"/v1beta/models/{self._settings.gemini_model}:generateContent",
                params={"key": self._settings.gemini_api_key},
                json=body,
                headers={"Content-Type": "application/json"},
            )
        except httpx.HTTPError:
            # Phủ cả timeout đọc lẫn mất kết nối. httpx không tự ném theo status code (khác
            # với `raise_for_status`), nên khối này chỉ bắt lỗi tầng vận chuyển — không có
            # lỗi HTTP nào lọt vào đây và bị gán nhầm nhãn.
            raise AppError.of(ErrorCode.GEMINI_UNAVAILABLE, "Gemini không phản hồi kịp") from None

        status = response.status_code
        if status == 429:
            raise AppError.of(ErrorCode.GEMINI_QUOTA, "Đã hết quota Gemini")
        if status >= 500:
            raise AppError.of(ErrorCode.GEMINI_UNAVAILABLE, f"Gemini trả lỗi HTTP {status}")
        if status >= 400:
            # Lỗi cấu hình phía ta (key sai, model sai) — retry không bao giờ cứu được, nên
            # KHÔNG map vào GEMINI_UNAVAILABLE (sẽ bị coi là retryable và bị retry vô ích).
            raise AppError.of(
                ErrorCode.INTERNAL,
                f"Gemini từ chối request (HTTP {status}). "
                "Kiểm tra GEMINI_API_KEY và GEMINI_MODEL trong file .env.",
            )
        return self._extract_payload(response.text)

    @staticmethod
    def _extract_payload(raw_body: str) -> Any:
        try:
            root = json.loads(raw_body)
            candidates = root.get("candidates") if isinstance(root, dict) else None
            if not isinstance(candidates, list) or not candidates:
                raise AppError.of(ErrorCode.PARSE_ERROR, "Gemini không trả candidate nào")
            first = candidates[0]
            inner = (
                first.get("content", {}).get("parts", [{}])[0].get("text")
                if isinstance(first, dict)
                else None
            )
            if inner is None:
                raise AppError.of(ErrorCode.PARSE_ERROR, "Gemini trả candidate rỗng")
            return json.loads(inner)
        except AppError:
            raise
        except Exception:
            raise AppError.of(ErrorCode.PARSE_ERROR, "Không đọc được JSON từ Gemini") from None

    def close(self) -> None:
        for client in self._clients.values():
            client.close()
        self._clients.clear()


@lru_cache(maxsize=1)
def get_gemini_client() -> GeminiClient:
    return GeminiClient()


def reset_gemini_client_cache() -> None:
    """Chỉ dùng trong test: buộc dựng lại client sau khi đổi GEMINI_BASE_URL."""
    get_gemini_client.cache_clear()
