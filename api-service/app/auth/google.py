"""Đổi authorization code lấy danh tính Google — bản port của `GoogleTokenClient`.

Việc đổi code nằm ở BACKEND chứ không ở extension, và đó là quyết định trung tâm của cả
tính năng: token đi thẳng từ token endpoint của Google về đây qua TLS, xác thực bằng
client_secret. Nếu extension tự đổi rồi gửi id_token lên thì backend buộc phải verify chữ
ký RS256 qua JWKS — code bảo mật không nên tự viết, và viết đúng thì phải kéo thêm thư viện
(ràng buộc #12).
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from functools import lru_cache

import httpx

from app.auth.models import GoogleIdentity
from app.common.errors import AppError, ErrorCode
from app.config import Settings, get_settings

log = logging.getLogger(__name__)

# Ngắn hơn hẳn Gemini vì đây là một lượt đổi token, không phải sinh văn bản: Google trả
# trong vài trăm ms hoặc là hỏng. Chờ 30 giây chỉ làm người dùng nhìn màn đăng nhập treo lâu
# hơn trước khi nhận đúng cái lỗi đó.
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 10.0


def _decode_segment(segment: str) -> bytes:
    """Giải mã một segment JWT theo base64url.

    Đệm `=` phải tự thêm. `Base64.getUrlDecoder()` của Java chấp nhận chuỗi thiếu đệm, còn
    `base64.urlsafe_b64decode` của Python thì ném `binascii.Error`. Payload JWT gần như
    luôn thiếu đệm, nên bỏ bước này là **mọi lượt đăng nhập đều hỏng** — và hỏng với thông
    điệp "Không đọc được id_token của Google", nghe như lỗi phía Google.
    """
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


class GoogleTokenClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: httpx.Client | None = None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._settings.auth_google_token_url,
                timeout=httpx.Timeout(
                    connect=CONNECT_TIMEOUT_SECONDS,
                    read=READ_TIMEOUT_SECONDS,
                    write=CONNECT_TIMEOUT_SECONDS,
                    pool=CONNECT_TIMEOUT_SECONDS,
                ),
            )
        return self._client

    def exchange(self, code: str, redirect_uri: str) -> GoogleIdentity:
        """`redirect_uri` PHẢI là chuỗi backend tự dựng từ EXTENSION_ID, không phải chuỗi
        client gửi lên. `AuthService` đã so trước khi gọi vào đây; bỏ bước đó là cho một
        extension lạ mượn client_secret của mình."""
        form = {
            "code": code,
            "client_id": self._settings.auth_google_client_id,
            "client_secret": self._settings.auth_google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            response = self._http().post("/token", data=form)
        except httpx.HTTPError:
            # KHÔNG đưa exception vào message: form body chứa client_secret và một số client
            # HTTP nhét nguyên request vào thông điệp lỗi.
            log.warning("Không gọi được Google token endpoint")
            raise AppError.of(ErrorCode.AUTH_UNAVAILABLE, "Google đang không phản hồi") from None

        status = response.status_code
        if status in (400, 401):
            # Code hết hạn, đã dùng, hoặc redirect_uri không khớp. Đây là lỗi của REQUEST,
            # không phải của Google — trả AUTH_UNAVAILABLE ở đây sẽ mời người dùng thử lại
            # một việc không bao giờ thành công.
            log.warning("Google từ chối authorization code (HTTP %d)", status)
            raise AppError.of(
                ErrorCode.UNAUTHORIZED, "Mã đăng nhập không hợp lệ hoặc đã hết hạn"
            )
        if status >= 500 or status == 429:
            raise AppError.of(ErrorCode.AUTH_UNAVAILABLE, "Google đang không phản hồi")
        if status != 200:
            raise AppError.of(ErrorCode.UNAUTHORIZED, f"Google trả mã không mong đợi: {status}")

        return self._parse(self._read_id_token(response.text))

    @staticmethod
    def _read_id_token(body: str | None) -> str:
        try:
            payload = json.loads(body or "")
            id_token = payload.get("id_token", "") if isinstance(payload, dict) else ""
            if not id_token or not str(id_token).strip():
                raise AppError.of(ErrorCode.UNAUTHORIZED, "Google không trả id_token")
            return str(id_token)
        except AppError:
            raise
        except Exception:
            raise AppError.of(
                ErrorCode.UNAUTHORIZED, "Không đọc được phản hồi từ Google"
            ) from None

    @staticmethod
    def _parse(id_token: str) -> GoogleIdentity:
        """Đọc payload của JWT mà KHÔNG verify chữ ký.

        Hợp lệ ĐÚNG trong tình huống này và không nơi nào khác: token vừa đi thẳng từ token
        endpoint của Google về đây qua TLS, và mình đã tự xác thực với Google bằng
        client_secret. Tài liệu OpenID Connect của Google nói rõ chỗ này.

        NẾU sau này token đến từ client thay vì từ token endpoint, PHẢI verify RS256 qua
        JWKS. Sửa chỗ nhận token mà quên chỗ này là biến "đăng nhập" thành "khai mình là ai
        cũng được".
        """
        parts = id_token.split(".")
        if len(parts) != 3:
            raise AppError.of(ErrorCode.UNAUTHORIZED, "Google trả id_token không hợp lệ")
        try:
            claims = json.loads(_decode_segment(parts[1]).decode("utf-8"))
            if not isinstance(claims, dict):
                raise ValueError("payload không phải object")
            sub = str(claims.get("sub", "") or "")
            email = str(claims.get("email", "") or "")
            if not sub.strip() or not email.strip():
                raise AppError.of(ErrorCode.UNAUTHORIZED, "id_token thiếu sub hoặc email")
            return GoogleIdentity(
                sub=sub,
                email=email.lower(),
                email_verified=bool(claims.get("email_verified", False)),
                name=claims.get("name"),
                picture=claims.get("picture"),
            )
        except AppError:
            raise
        except (ValueError, binascii.Error, UnicodeDecodeError):
            raise AppError.of(
                ErrorCode.UNAUTHORIZED, "Không đọc được id_token của Google"
            ) from None


@lru_cache(maxsize=1)
def get_google_client() -> GoogleTokenClient:
    return GoogleTokenClient()


def reset_google_client_cache() -> None:
    """Chỉ dùng trong test: buộc dựng lại client sau khi đổi AUTH_GOOGLE_TOKEN_URL."""
    get_google_client.cache_clear()
