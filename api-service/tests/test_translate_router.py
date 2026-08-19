"""Bản port của `TranslateControllerIT`.

Đây là hợp đồng HTTP mà extension đọc: status code, tên field, và hình dạng lỗi
`{code, message, retryable}` (ràng buộc #4). Bên Java, `GeminiClient` bị `@MockitoBean` và
test ném thẳng `AppException` từ mock; ở đây `gemini` trả **status HTTP thô** và để
`GeminiClient` thật tự map sang `ErrorCode` — nên mỗi test dưới đây kiểm luôn cả bảng ánh xạ
đó, thứ bản Java bỏ qua vì đã mock mất.

**Thứ tự fixture:** `client` LUÔN đứng trước `gemini`. `TestClient` là một `httpx.Client`, mà
`gemini` vá `httpx.Client.__init__` để nhét transport giả vào — dựng TestClient sau bản vá
thì mọi request tới ứng dụng sẽ bay vào transport giả thay vì vào FastAPI.
"""

from __future__ import annotations

from typing import Any

from app.translation.service import MAX_TEXT_LENGTH
from tests.conftest import FakeGemini, UserFixture


def test_returns_direction_mode_and_payload(
    client: Any, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Hình dạng phản hồi thành công — bốn khoá, tên camelCase như Jackson phát ra.

    `direction` + `mode` là thứ bubble phân nhánh để chọn template hiển thị, `cached` là thứ
    side panel dùng để biết lượt tra này có tốn quota hay không.
    """
    gemini.queue_json({"meaning_vi": "tái tạo"})

    resp = client.post(
        "/api/translate",
        headers=owner.headers,
        json={"text": "renewable", "contextSentence": "We need renewable energy."},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["direction"] == "EN_VI"
    assert body["mode"] == "WORD"
    assert body["cached"] is False
    assert body["payload"]["meaning_vi"] == "tái tạo"


def test_quota_exhausted_returns_429_with_correct_error_shape(
    client: Any, gemini: FakeGemini, owner: UserFixture
) -> None:
    """429 của Gemini → GEMINI_QUOTA → 429 của ta, và KHÔNG retryable.

    Bảo người dùng "thử lại sau ít giây" khi quota đã cạn là chỉ sai đường hồi phục. Cũng vì
    thế `GeminiClient` không được retry mã này: chỉ xếp MỘT phản hồi 429, lượt gọi thứ hai
    sẽ làm transport giả nổ.
    """
    gemini.queue_status(429)

    resp = client.post("/api/translate", headers=owner.headers, json={"text": "renewable"})

    assert resp.status_code == 429, resp.text
    body = resp.json()
    assert body["code"] == "GEMINI_QUOTA"
    assert body["retryable"] is False
    assert body["message"]
    assert gemini.call_count == 1


def test_gemini_down_returns_503_and_is_marked_retryable(
    client: Any, gemini: FakeGemini, owner: UserFixture
) -> None:
    """5xx của Gemini → GEMINI_UNAVAILABLE → 503, retryable = true.

    Hai phản hồi 503 chứ không một: lỗi tạm thời được retry đúng một lần (`MAX_ATTEMPTS=2`),
    và số lượt gọi cũng là một khẳng định — retry ba lần thì mỗi sự cố bên Gemini nhân ba
    tải lên chính nó.
    """
    gemini.queue_status(503, times=2)

    resp = client.post("/api/translate", headers=owner.headers, json={"text": "renewable"})

    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["code"] == "GEMINI_UNAVAILABLE"
    assert body["retryable"] is True
    assert gemini.call_count == 2


def test_text_over_limit_returns_400(
    client: Any, gemini: FakeGemini, owner: UserFixture
) -> None:
    """1501 ký tự → TEXT_TOO_LONG → 400, và không một byte nào đi tới Gemini."""
    resp = client.post(
        "/api/translate",
        headers=owner.headers,
        json={"text": "a" * (MAX_TEXT_LENGTH + 1)},
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "TEXT_TOO_LONG"
    assert gemini.requests == []


def test_whitespace_only_text_fails_validation_and_returns_400(
    client: Any, gemini: FakeGemini, owner: UserFixture
) -> None:
    """400 chứ không 422, và thông điệp bằng TIẾNG VIỆT.

    Hai vế đều là hợp đồng thật, không phải thẩm mỹ: extension phân nhánh theo status code
    nên 422 mặc định của FastAPI làm hỏng phía client mà không có gì đỏ ở đây; còn `message`
    được bubble hiển thị NGUYÊN VĂN cho người dùng, nên "must not be blank" là để lộ thông
    điệp mặc định của framework ra tận màn hình.
    """
    resp = client.post("/api/translate", headers=owner.headers, json={"text": "   "})

    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["code"] == "INTERNAL"
    assert body["retryable"] is False
    assert "không được để trống" in body["message"]
    assert "must not be blank" not in body["message"]
    assert gemini.requests == []
