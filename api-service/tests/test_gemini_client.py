"""Bản port của `GeminiClientTest`. WireMock thay bằng transport giả của httpx."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.common.errors import AppError, ErrorCode
from app.common.gemini import GeminiClient, GeminiTimeout
from app.config import Settings
from tests.conftest import GeminiGia, _boc_candidate, _TransportGia

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"meaning_vi": {"type": "string"}},
}


def _dung_client(gia: GeminiGia, **ghi_de: Any) -> GeminiClient:
    settings = Settings(
        GEMINI_API_KEY="test-key",
        GEMINI_MODEL="gemini-2.5-flash",
        GEMINI_BASE_URL="http://gemini.test",
        GEMINI_RETRY_BACKOFF_MS=0,
        **ghi_de,
    )
    client = GeminiClient(settings)
    # Nạp sẵn ba client với transport giả để `_client()` không tự dựng client thật.
    for tier in GeminiTimeout:
        client._clients[tier] = httpx.Client(
            base_url=settings.gemini_base_url, transport=_TransportGia(gia)
        )
    return client


@pytest.fixture
def gia() -> GeminiGia:
    return GeminiGia()


def test_tra_ve_json_da_parse_khi_thanh_cong(gia: GeminiGia) -> None:
    gia.tra_json({"meaning_vi": "tái tạo"})

    ket_qua = _dung_client(gia).generate_json("prompt bất kỳ", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ket_qua["meaning_vi"] == "tái tạo"


def test_gui_dung_api_key_va_response_schema(gia: GeminiGia) -> None:
    gia.tra_json({"meaning_vi": "x"})

    _dung_client(gia).generate_json("prompt bất kỳ", SCHEMA, GeminiTimeout.TRANSLATE)

    req = gia.requests[0]
    assert req.url.path == "/v1beta/models/gemini-2.5-flash:generateContent"
    assert req.url.params["key"] == "test-key"
    body = json.loads(req.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseSchema"] == SCHEMA
    assert body["contents"][0]["parts"][0]["text"] == "prompt bất kỳ"
    assert body["contents"][0]["role"] == "user"


def test_loi_quota_khong_retry_va_map_sang_gemini_quota(gia: GeminiGia) -> None:
    gia.tra_status(429, '{"error":{"message":"quota exceeded"}}')

    with pytest.raises(AppError) as ex:
        _dung_client(gia).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.GEMINI_QUOTA
    assert ex.value.retryable is False
    assert gia.so_lan_goi == 1


@pytest.mark.parametrize("status", [400, 401, 404])
def test_loi_cau_hinh_khong_retry_va_map_sang_internal(gia: GeminiGia, status: int) -> None:
    """Key sai / model sai: retry không bao giờ cứu được, nên KHÔNG map vào
    GEMINI_UNAVAILABLE (sẽ bị coi là retryable và bị retry vô ích)."""
    gia.tra_status(status, '{"error":{"message":"sai cấu hình"}}')

    with pytest.raises(AppError) as ex:
        _dung_client(gia).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.INTERNAL
    assert ex.value.retryable is False
    assert gia.so_lan_goi == 1


def test_loi_server_duoc_retry_mot_lan_roi_bo_cuoc(gia: GeminiGia) -> None:
    gia.tra_status(503, '{"error":"unavailable"}', lap=2)

    with pytest.raises(AppError) as ex:
        _dung_client(gia).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.GEMINI_UNAVAILABLE
    assert gia.so_lan_goi == 2


def test_loi_server_hoi_phuc_o_lan_thu_hai_thi_thanh_cong(gia: GeminiGia) -> None:
    gia.tra_status(503, "{}")
    gia.tra_json({"meaning_vi": "ổn"})

    ket_qua = _dung_client(gia).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ket_qua["meaning_vi"] == "ổn"
    assert gia.so_lan_goi == 2


def test_json_ben_trong_hong_duoc_retry_roi_map_sang_parse_error(gia: GeminiGia) -> None:
    gia.tra_text("khong phai json")
    gia.tra_text("khong phai json")

    with pytest.raises(AppError) as ex:
        _dung_client(gia).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.PARSE_ERROR
    assert gia.so_lan_goi == 2


def test_thieu_candidates_map_sang_parse_error(gia: GeminiGia) -> None:
    gia.tra_raw(httpx.Response(200, json={"candidates": []}))
    gia.tra_raw(httpx.Response(200, json={"candidates": []}))

    with pytest.raises(AppError) as ex:
        _dung_client(gia).generate_json("p", SCHEMA, GeminiTimeout.TRANSLATE)

    assert ex.value.code is ErrorCode.PARSE_ERROR
    assert gia.so_lan_goi == 2


def test_timeout_map_sang_gemini_unavailable(gia: GeminiGia) -> None:
    class _TimeoutTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            gia.requests.append(request)
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
    assert gia.so_lan_goi == 2


def test_moi_muc_timeout_dung_dung_cau_hinh_cua_no() -> None:
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


def test_boc_candidate_khop_hinh_dang_that_cua_gemini() -> None:
    """Chốt lại đường đọc `candidates[0].content.parts[0].text`. Đây là hình dạng thật của
    response Gemini; đổi nó là mọi lượt gọi trả PARSE_ERROR."""
    resp = _boc_candidate({"a": 1})
    payload = resp.json()
    assert json.loads(payload["candidates"][0]["content"]["parts"][0]["text"]) == {"a": 1}
