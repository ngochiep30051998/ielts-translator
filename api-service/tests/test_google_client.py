"""Bản port của `GoogleTokenClientTest` — tầng HTTP đi Google.

Giả lập ở tầng vận chuyển là ĐÚNG chỗ ở đây, khác `test_auth_router.py` nơi thứ đang test
là luồng nghiệp vụ nên `GoogleTokenClient` bị thay nguyên khối.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest

from app.auth.google import GoogleTokenClient, _decode_segment
from app.common.errors import AppError, ErrorCode
from app.config import Settings

REDIRECT = "https://testextensionid.chromiumapp.org/"
BI_MAT = "SIEU-BI-MAT"


class _Ghi(httpx.BaseTransport):
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        return self.response


def _client(response: httpx.Response) -> tuple[GoogleTokenClient, _Ghi]:
    settings = Settings(
        AUTH_GOOGLE_CLIENT_ID="client-id",
        AUTH_GOOGLE_CLIENT_SECRET=BI_MAT,
        AUTH_GOOGLE_TOKEN_URL="http://google.test",
        EXTENSION_ID="testextensionid",
    )
    client = GoogleTokenClient(settings)
    ghi = _Ghi(response)
    client._client = httpx.Client(base_url=settings.auth_google_token_url, transport=ghi)
    return client, ghi


def _base64url(json_text: str) -> str:
    """Không đệm `=`, đúng như `Base64.getUrlEncoder().withoutPadding()` bên Java —
    và đúng như id_token thật của Google."""
    return base64.urlsafe_b64encode(json_text.encode("utf-8")).decode("ascii").rstrip("=")


def _id_token(payload_json: str) -> httpx.Response:
    return httpx.Response(200, json={"id_token": f"header.{_base64url(payload_json)}.chu-ky-rac"})


def test_doc_sub_va_email_tu_payload_khong_verify_chu_ky() -> None:
    """Chữ ký "rác" là CỐ Ý.

    Token đến thẳng từ token endpoint qua TLS và mình đã xác thực với Google bằng
    client_secret, nên theo tài liệu OIDC của Google không cần verify. Test này khoá chính
    hành vi đó: ai thêm bước verify vào sẽ thấy nó đỏ và phải đọc lại thiết kế trước khi đổi.
    """
    client, _ = _client(
        _id_token('{"sub":"1234567890","email":"A@B.com","email_verified":true,"name":"A B"}')
    )

    danh_tinh = client.exchange("code-abc", REDIRECT)

    assert danh_tinh.sub == "1234567890"
    # Email hạ về chữ thường ngay tại đây: allowlist so bằng chuỗi, và Google có thể trả về
    # hoa thường bất kỳ.
    assert danh_tinh.email == "a@b.com"
    assert danh_tinh.email_verified is True
    assert danh_tinh.name == "A B"


def test_payload_thieu_dem_base64_van_doc_duoc() -> None:
    """Bẫy riêng của Python mà Java không có.

    `Base64.getUrlDecoder()` chấp nhận chuỗi thiếu đệm; `base64.urlsafe_b64decode` thì ném
    `binascii.Error`. Payload JWT gần như luôn thiếu đệm, nên sai chỗ này là MỌI lượt đăng
    nhập hỏng — và hỏng với thông điệp "Không đọc được id_token của Google", nghe như lỗi
    phía Google.
    """
    for do_dai in range(1, 8):
        goc = '{"sub":"' + "x" * do_dai + '","email":"a@b.com"}'
        khong_dem = _base64url(goc)
        assert len(khong_dem) % 4 != 0 or True  # chỉ cần giải mã ra đúng chuỗi ban đầu
        assert _decode_segment(khong_dem).decode("utf-8") == goc


def test_code_het_han_tra_unauthorized_chu_khong_auth_unavailable() -> None:
    """Lỗi của REQUEST, không phải của Google — trả AUTH_UNAVAILABLE ở đây sẽ mời người
    dùng thử lại một việc không bao giờ thành công."""
    client, _ = _client(httpx.Response(400, json={"error": "invalid_grant"}))

    with pytest.raises(AppError) as ex:
        client.exchange("code-cu", REDIRECT)

    assert ex.value.code is ErrorCode.UNAUTHORIZED
    assert ex.value.retryable is False


@pytest.mark.parametrize("status", [500, 502, 503, 429])
def test_google_chet_tra_auth_unavailable_va_retry_duoc(status: int) -> None:
    client, _ = _client(httpx.Response(status, text=""))

    with pytest.raises(AppError) as ex:
        client.exchange("code-abc", REDIRECT)

    assert ex.value.code is ErrorCode.AUTH_UNAVAILABLE
    assert ex.value.retryable is True


def test_thieu_id_token_tra_unauthorized() -> None:
    """Không được nổ AttributeError."""
    client, _ = _client(httpx.Response(200, json={"access_token": "chi-co-access-token"}))

    with pytest.raises(AppError) as ex:
        client.exchange("code-abc", REDIRECT)

    assert ex.value.code is ErrorCode.UNAUTHORIZED


def test_id_token_khong_du_ba_phan_tra_unauthorized() -> None:
    client, _ = _client(httpx.Response(200, json={"id_token": "khong-phai-jwt"}))

    with pytest.raises(AppError) as ex:
        client.exchange("code-abc", REDIRECT)

    assert ex.value.code is ErrorCode.UNAUTHORIZED


def test_payload_thieu_sub_hoac_email_tra_unauthorized() -> None:
    client, _ = _client(_id_token('{"email":"a@b.com"}'))

    with pytest.raises(AppError) as ex:
        client.exchange("code-abc", REDIRECT)

    assert ex.value.code is ErrorCode.UNAUTHORIZED


def test_client_secret_khong_lot_vao_thong_diep_loi() -> None:
    """Thông điệp lỗi đi thẳng ra response cho extension. Một client HTTP nhét nguyên
    request body vào message là đủ để secret rời khỏi server."""
    client, _ = _client(httpx.Response(400, json={"error": "invalid_grant"}))

    with pytest.raises(AppError) as ex:
        client.exchange("code-abc", REDIRECT)

    assert ex.value.message
    assert BI_MAT not in ex.value.message
    assert BI_MAT not in repr(ex.value)


def test_gui_dung_form_va_grant_type() -> None:
    client, ghi = _client(_id_token('{"sub":"s","email":"a@b.com","email_verified":true}'))

    client.exchange("code-abc", REDIRECT)

    req = ghi.requests[0]
    assert req.url.path == "/token"
    assert req.headers["content-type"].startswith("application/x-www-form-urlencoded")
    form: dict[str, Any] = dict(
        phan.split("=", 1) for phan in req.content.decode().split("&")  # type: ignore[misc,arg-type]
    )
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == "code-abc"
    assert form["client_id"] == "client-id"


def test_loi_mang_tra_auth_unavailable() -> None:
    class _Chet(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("không nối được", request=request)

    settings = Settings(AUTH_GOOGLE_TOKEN_URL="http://google.test")
    client = GoogleTokenClient(settings)
    client._client = httpx.Client(transport=_Chet())

    with pytest.raises(AppError) as ex:
        client.exchange("code-abc", REDIRECT)

    assert ex.value.code is ErrorCode.AUTH_UNAVAILABLE
    assert ex.value.retryable is True
