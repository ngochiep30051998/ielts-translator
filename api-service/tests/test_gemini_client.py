"""Bản port của `GeminiClientTest`. WireMock thay bằng transport giả của httpx."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.common.errors import AppError, ErrorCode
from app.common.gemini import GeminiClient, GeminiTimeout
from app.config import Settings
from tests.conftest import FakeGemini, _FakeTransport, _wrap_candidate

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"meaning_vi": {"type": "string"}},
}


def _build_client(fake_gemini: FakeGemini, **overrides: Any) -> GeminiClient:
    settings = Settings(
        GEMINI_API_KEY="test-key",
        GEMINI_MODEL="gemini-2.5-flash",
        GEMINI_BASE_URL="http://gemini.test",
        GEMINI_RETRY_BACKOFF_MS=0,
        **overrides,
    )
    client = GeminiClient(settings)
    # Nạp sẵn ba client với transport giả để `_client()` không tự dựng client thật.
    for tier in GeminiTimeout:
        client._clients[tier] = httpx.Client(
            base_url=settings.gemini_base_url, transport=_FakeTransport(fake_gemini)
        )
    return client


@pytest.fixture
def fake_gemini() -> FakeGemini:
    return FakeGemini()


def test_returns_parsed_json_on_success(fake_gemini: FakeGemini) -> None:
    fake_gemini.queue_json({"meaning_vi": "tái tạo"})

    result = _build_client(fake_gemini).generate_json(
        "prompt bất kỳ", SCHEMA, GeminiTimeout.TRANSLATE
    )

    assert result["meaning_vi"] == "tái tạo"


def test_sends_correct_api_key_and_response_schema(fake_gemini: FakeGemini) -> None:
    fake_gemini.queue_json({"meaning_vi": "x"})

    _build_client(fake_gemini).generate_json("prompt bất kỳ", SCHEMA, GeminiTimeout.TRANSLATE)

    req = fake_gemini.requests[0]
    assert req.url.path == "/v1beta/models/gemini-2.5-flash:generateContent"
    assert req.url.params["key"] == "test-key"
    body = json.loads(req.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseSchema"] == SCHEMA
    assert body["contents"][0]["parts"][0]["text"] == "prompt bất kỳ"
    assert body["contents"][0]["role"] == "user"


def test_quota_error_not_retried_and_mapped_to_gemini_quota(fake_gemini: FakeGemini) -> None:
    fake_gemini.queue_status(429, '{"error":{"message":"quota exceeded"}}')

    with pytest.raises(AppError) as ex:
        _build_client(fake_gemini).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.GEMINI_QUOTA
    assert ex.value.retryable is False
    assert fake_gemini.call_count == 1


@pytest.mark.parametrize("status", [400, 401, 404])
def test_config_error_not_retried_and_mapped_to_internal(
    fake_gemini: FakeGemini, status: int
) -> None:
    """Key sai / model sai: retry không bao giờ cứu được, nên KHÔNG map vào
    GEMINI_UNAVAILABLE (sẽ bị coi là retryable và bị retry vô ích)."""
    fake_gemini.queue_status(status, '{"error":{"message":"sai cấu hình"}}')

    with pytest.raises(AppError) as ex:
        _build_client(fake_gemini).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.INTERNAL
    assert ex.value.retryable is False
    assert fake_gemini.call_count == 1


def test_server_error_retried_once_then_gives_up(fake_gemini: FakeGemini) -> None:
    fake_gemini.queue_status(503, '{"error":"unavailable"}', times=2)

    with pytest.raises(AppError) as ex:
        _build_client(fake_gemini).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.GEMINI_UNAVAILABLE
    assert fake_gemini.call_count == 2


def test_server_error_recovering_on_second_attempt_succeeds(fake_gemini: FakeGemini) -> None:
    fake_gemini.queue_status(503, "{}")
    fake_gemini.queue_json({"meaning_vi": "ổn"})

    result = _build_client(fake_gemini).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert result["meaning_vi"] == "ổn"
    assert fake_gemini.call_count == 2


def test_broken_inner_json_is_retried_then_mapped_to_parse_error(fake_gemini: FakeGemini) -> None:
    fake_gemini.queue_text("khong phai json")
    fake_gemini.queue_text("khong phai json")

    with pytest.raises(AppError) as ex:
        _build_client(fake_gemini).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.PARSE_ERROR
    assert fake_gemini.call_count == 2


def test_missing_candidates_maps_to_parse_error(fake_gemini: FakeGemini) -> None:
    fake_gemini.queue_raw(httpx.Response(200, json={"candidates": []}))
    fake_gemini.queue_raw(httpx.Response(200, json={"candidates": []}))

    with pytest.raises(AppError) as ex:
        _build_client(fake_gemini).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.PARSE_ERROR
    assert fake_gemini.call_count == 2


def test_timeout_maps_to_gemini_unavailable(fake_gemini: FakeGemini) -> None:
    class _TimeoutTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            fake_gemini.requests.append(request)
            raise httpx.ReadTimeout("quá hạn đọc", request=request)

    settings = Settings(
        GEMINI_API_KEY="k", GEMINI_BASE_URL="http://x.test", GEMINI_RETRY_BACKOFF_MS=0
    )
    client = GeminiClient(settings)
    for tier in GeminiTimeout:
        client._clients[tier] = httpx.Client(transport=_TimeoutTransport())

    with pytest.raises(AppError) as ex:
        client.generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.GEMINI_UNAVAILABLE
    assert fake_gemini.call_count == 2


def test_each_timeout_tier_uses_its_own_setting() -> None:
    """Ba mức khác nhau vì độ dài output khác nhau một bậc: dịch một từ trả vài trăm token,
    sinh một lô 10 câu quiz trả vài nghìn.

    Bên Java phải có ba `RestClient` vì read-timeout nướng vào request factory. Ở đây kiểm
    trực tiếp rằng mỗi mức đọc đúng biến cấu hình của nó — sai chỗ này thì một lượt sinh
    quiz chạy ở mức 15 giây: biên dịch sạch, test xanh, chỉ hỏng trên máy người dùng khi
    Gemini chậm thật.
    """
    settings = Settings(
        GEMINI_TIMEOUT_SECONDS=15,
        GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS=30,
        GEMINI_QUIZ_GRADE_TIMEOUT_SECONDS=20,
    )
    client = GeminiClient(settings)

    assert client._client(GeminiTimeout.TRANSLATE).timeout.read == 15
    assert client._client(GeminiTimeout.QUIZ_GENERATE).timeout.read == 30
    assert client._client(GeminiTimeout.QUIZ_GRADE).timeout.read == 20
    # Bắt tay TCP không phụ thuộc độ dài output nên dùng chung cho cả ba mức.
    assert client._client(GeminiTimeout.TRANSLATE).timeout.connect == 5
    client.close()


def test_candidate_wrapper_matches_real_gemini_response_shape() -> None:
    """Chốt lại đường đọc `candidates[0].content.parts[0].text`. Đây là hình dạng thật của
    response Gemini; đổi nó là mọi lượt gọi trả PARSE_ERROR."""
    resp = _wrap_candidate({"a": 1})
    payload = resp.json()
    assert json.loads(payload["candidates"][0]["content"]["parts"][0]["text"]) == {"a": 1}
