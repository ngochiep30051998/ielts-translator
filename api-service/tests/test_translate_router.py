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
from tests.conftest import GeminiGia, NguoiDungTest


def test_tra_ve_direction_mode_va_payload(
    client: Any, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Hình dạng phản hồi thành công — bốn khoá, tên camelCase như Jackson phát ra.

    `direction` + `mode` là thứ bubble phân nhánh để chọn template hiển thị, `cached` là thứ
    side panel dùng để biết lượt tra này có tốn quota hay không.
    """
    gemini.tra_json({"meaning_vi": "tái tạo"})

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


def test_het_quota_tra_429_dung_hinh_dang_loi(
    client: Any, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """429 của Gemini → GEMINI_QUOTA → 429 của ta, và KHÔNG retryable.

    Bảo người dùng "thử lại sau ít giây" khi quota đã cạn là chỉ sai đường hồi phục. Cũng vì
    thế `GeminiClient` không được retry mã này: chỉ xếp MỘT phản hồi 429, lượt gọi thứ hai
    sẽ làm transport giả nổ.
    """
    gemini.tra_status(429)

    resp = client.post("/api/translate", headers=owner.headers, json={"text": "renewable"})

    assert resp.status_code == 429, resp.text
    body = resp.json()
    assert body["code"] == "GEMINI_QUOTA"
    assert body["retryable"] is False
    assert body["message"]
    assert gemini.so_lan_goi == 1


def test_gemini_chet_tra_503_va_duoc_danh_dau_retryable(
    client: Any, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """5xx của Gemini → GEMINI_UNAVAILABLE → 503, retryable = true.

    Hai phản hồi 503 chứ không một: lỗi tạm thời được retry đúng một lần (`MAX_ATTEMPTS=2`),
    và số lượt gọi cũng là một khẳng định — retry ba lần thì mỗi sự cố bên Gemini nhân ba
    tải lên chính nó.
    """
    gemini.tra_status(503, lap=2)

    resp = client.post("/api/translate", headers=owner.headers, json={"text": "renewable"})

    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["code"] == "GEMINI_UNAVAILABLE"
    assert body["retryable"] is True
    assert gemini.so_lan_goi == 2


def test_text_vuot_gioi_han_tra_400(
    client: Any, gemini: GeminiGia, owner: NguoiDungTest
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


def test_text_toan_khoang_trang_truot_validate_va_tra_400(
    client: Any, gemini: GeminiGia, owner: NguoiDungTest
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
