"""Cookie phiên và cookie state của luồng đăng nhập web.

Extension KHÔNG dùng file này — nó mang token trong header `Authorization`. Mọi thứ ở đây
chỉ phục vụ web app chạy cùng origin với backend.
"""

from __future__ import annotations

from fastapi import Response

from app.config import Settings

#: Header bắt buộc để cookie phiên được chấp nhận. Xem docstring `session_token` ở `deps.py`.
WEB_CLIENT_HEADER = "X-IELTS-Web"

#: Đường dẫn của cookie. `__Host-` BẮT BUỘC `Path=/`, và `delete_cookie` phải truyền lại
#: đúng giá trị này — sai path thì trình duyệt coi là một cookie khác và không xoá gì cả.
COOKIE_PATH = "/"

_SESSION = "ielts_session"
_STATE = "ielts_oauth_state"

#: Cookie state sống đủ lâu cho một lượt đăng nhập, không hơn.
STATE_MAX_AGE_SECONDS = 600


def _ten(co_ban: str, settings: Settings) -> str:
    """Gắn tiền tố `__Host-` khi cookie là Secure.

    `__Host-` là thứ ngăn một subdomain ghi đè cookie của domain cha: cookie KHÔNG có tính
    toàn vẹn theo origin, nên bất kỳ subdomain nào của cùng registrable domain đều ghi đè
    được. Trên `*.vercel.app` đó không phải rủi ro lý thuyết.

    Tiền tố đòi `Secure` + `Path=/` + KHÔNG có `Domain`, nên khi chạy HTTP local (không
    Secure) phải bỏ nó đi — trình duyệt sẽ từ chối thẳng một cookie `__Host-` không Secure,
    và triệu chứng là đăng nhập "thành công" nhưng request sau vẫn 401.
    """
    return f"__Host-{co_ban}" if settings.cookie_secure else co_ban


def session_cookie_name(settings: Settings) -> str:
    return _ten(_SESSION, settings)


def state_cookie_name(settings: Settings) -> str:
    return _ten(_STATE, settings)


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    """Phát cookie phiên.

    `SameSite=Lax`, KHÔNG phải Strict: cookie này được set trong response của callback rồi
    trình duyệt đi tiếp tới `/` — Strict sẽ không gửi nó trong lượt điều hướng đó và người
    dùng quay lại màn đăng nhập ngay sau khi đăng nhập xong.

    Lax là lớp phòng thủ thứ hai chứ không phải thứ nhất: chốt chặn CSRF thật nằm ở header
    bắt buộc `X-IELTS-Web` (xem `deps.session_token`).
    """
    response.set_cookie(
        key=session_cookie_name(settings),
        value=token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=session_cookie_name(settings),
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def set_state_cookie(response: Response, state: str, settings: Settings) -> None:
    """Phát cookie state cho một lượt đăng nhập.

    Cũng phải là `Lax` chứ KHÔNG Strict, và đây là chỗ dễ "siết cho an toàn" nhất trong cả
    tính năng: redirect từ `accounts.google.com` về callback là điều hướng CROSS-SITE, nên
    Strict = cookie không được gửi = **100% lượt đăng nhập hỏng** — hỏng theo kiểu trông y
    hệt lỗi phía Google, nên áp lực sửa sẽ đẩy đi sai hướng.
    """
    response.set_cookie(
        key=state_cookie_name(settings),
        value=state,
        max_age=STATE_MAX_AGE_SECONDS,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_state_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=state_cookie_name(settings),
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
