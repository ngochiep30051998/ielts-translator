"""POST /api/auth/google · GET /api/auth/me · POST /api/auth/logout
· GET /api/auth/google/start · GET /api/auth/google/callback

Hai nhóm endpoint, hai kiểu client hoàn toàn khác nhau:

- `POST /google` là của **extension**: nó tự mở cửa sổ OAuth bằng `chrome.identity`, rồi gửi
  `code` lên đây và nhận token trong JSON body.
- `/google/start` + `/google/callback` là của **web app**: trình duyệt điều hướng cả trang,
  nên token không thể đi qua body — nó đi bằng cookie httpOnly, và JavaScript không bao giờ
  nhìn thấy nó.
"""

from __future__ import annotations

import secrets
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from app.auth.cookies import (
    clear_session_cookie,
    clear_state_cookie,
    set_session_cookie,
    set_state_cookie,
    state_cookie_name,
)
from app.auth.deps import CurrentUserId, Db, cookie_token, session_token
from app.auth.models import AuthSessionDto, AuthUserDto, GoogleLoginRequest
from app.auth.service import AuthService, get_auth_service
from app.common.errors import AppError, ErrorCode
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

#: Đích sau khi đăng nhập xong. HẰNG SỐ, không bao giờ lấy từ tham số.
#:
#: Chưa có `?next=` nên chưa có open redirect — và chốt nó thành hằng ở đây là cách rẻ nhất
#: để người sau muốn thêm `?next=` phải sửa đúng chỗ này và đọc dòng chú thích này trước.
#: Biến thể hay bị quên khi lọc tay: `//evil.com`, `/\evil.com`, `%2f%2fevil.com`.
WEB_HOME = "/"


@router.post("/google", response_model=AuthSessionDto)
def google(
    request: GoogleLoginRequest,
    db: Db,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionDto:
    """Công khai — đây là đường DUY NHẤT để có token, nên nó không thể đòi token."""
    return service.login(db, request.code, request.redirect_uri)


@router.get("/google/start")
def google_start(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    """Mở luồng đăng nhập của web: sinh state, gửi trình duyệt sang Google."""
    settings = get_settings()
    if not settings.web_base_url.strip():
        # Fail closed, và nói ra là lỗi CẤU HÌNH. Bẫy có sẵn ở ngay cạnh: EXTENSION_ID rỗng
        # sinh ra `https://.chromiumapp.org/` — một chuỗi hợp lệ về cú pháp, nên cấu hình
        # thiếu không nổ, chỉ làm mọi lượt đăng nhập 401 mà không ai hiểu vì sao.
        raise AppError.of(
            ErrorCode.AUTH_UNAVAILABLE, "Chưa cấu hình WEB_BASE_URL nên không mở được đăng nhập"
        )

    state = secrets.token_urlsafe(32)
    query = urlencode(
        {
            "client_id": settings.auth_google_client_id,
            "response_type": "code",
            # `openid` là BẮT BUỘC. Thiếu nó Google vẫn trả 200 kèm access_token nhưng KHÔNG
            # có id_token, và `google.py` sẽ ném "Google không trả id_token" — thông điệp
            # trỏ về phía Google trong khi lỗi nằm ở chuỗi scope của mình.
            "scope": "openid email profile",
            "redirect_uri": service.web_redirect_uri(),
            "state": state,
            # Thiếu select_account thì trình duyệt im lặng dùng lại tài khoản Google lần
            # trước — người có hai tài khoản không đổi được mà cũng không hiểu vì sao.
            "prompt": "select_account",
        }
    )

    response = RedirectResponse(f"{settings.auth_google_auth_url}?{query}", status_code=302)
    set_state_cookie(response, state, settings)
    return response


@router.get("/google/callback")
def google_callback(
    request: Request,
    db: Db,
    service: Annotated[AuthService, Depends(get_auth_service)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    """Google trả người dùng về đây. Kết thúc bằng redirect, không bao giờ bằng JSON.

    Người dùng đang ở GIỮA một lượt điều hướng trình duyệt: trả `{code, message, retryable}`
    ở đây là ném một khối JSON trần vào giữa màn hình. Mọi lỗi đều thành
    `/?authError=<MÃ>`, và SPA dịch mã đó ra tiếng Việt.
    """
    settings = get_settings()

    if error:
        return _redirect_home_with_error(ErrorCode.UNAUTHORIZED, settings)

    if not _state_matches(request, state, settings):
        return _redirect_home_with_error(ErrorCode.UNAUTHORIZED, settings)

    if not code:
        return _redirect_home_with_error(ErrorCode.UNAUTHORIZED, settings)

    try:
        session = service.login_web(db, code)
    except AppError as exc:
        # FORBIDDEN (email chưa được cấp quyền) là trạng thái VĨNH VIỄN và phải phân biệt
        # được với UNAUTHORIZED, vì cách hồi phục khác hẳn nhau: một bên bấm lại là xong,
        # bên kia phải nhờ quản trị thêm email.
        return _redirect_home_with_error(exc.code, settings)

    response = RedirectResponse(WEB_HOME, status_code=302)
    set_session_cookie(response, session.token, settings)
    clear_state_cookie(response, settings)
    return response


def _state_matches(request: Request, state: str | None, settings: Settings) -> bool:
    """So state gửi về với state đã phát, theo kiểu không có kẽ hở.

    Ba cái bẫy nằm gọn trong một hàm nhỏ:

    1. `state != cookie` viết trần sẽ cho qua khi **cả hai cùng vắng** (`None == None`).
       Nên phải đòi cả hai tồn tại và khác rỗng TRƯỚC khi so.
    2. `secrets.compare_digest` ném `TypeError` với ký tự ngoài ASCII, mà `state` do client
       điều khiển hoàn toàn — `?state=é` sẽ biến một 401 thành 500.
    3. So bằng `==` là so sánh không hằng thời gian. Ở đây rủi ro thấp, nhưng dùng đúng hàm
       thì không phải cân nhắc.
    """
    issued_state = request.cookies.get(state_cookie_name(settings))
    if not state or not issued_state:
        return False
    if not state.isascii() or not issued_state.isascii():
        return False
    return secrets.compare_digest(state, issued_state)


def _redirect_home_with_error(code: ErrorCode, settings: Settings) -> Response:
    response = RedirectResponse(f"{WEB_HOME}?authError={code.value}", status_code=302)
    clear_state_cookie(response, settings)
    return response


@router.get("/me", response_model=AuthUserDto)
def me(
    user_id: CurrentUserId,
    db: Db,
    service: Annotated[AuthService, Depends(get_auth_service)],
    response: Response,
    cookie: Annotated[str | None, Depends(cookie_token)] = None,
) -> AuthUserDto:
    """Cách client kiểm token còn sống, thay vì đợi một request nghiệp vụ nào đó nhận 401.

    Nhân tiện làm mới hạn cookie. Hai đồng hồ đang chạy lệch nhau: `resolve_user_id` gia hạn
    `expires_at` trong DB mỗi ngày dùng, còn `Max-Age` của cookie đóng băng lúc phát — nên
    người vào hàng ngày vẫn bị đá ra đúng ngày thứ 60. Web gọi endpoint này mỗi lần mở app
    (nó không có storage để đọc user như extension), nên đây là chỗ rẻ nhất để phát lại.
    """
    if cookie:
        set_session_cookie(response, cookie, get_settings())
    return service.me(db, user_id)


@router.post("/logout", status_code=204)
def logout(
    # `user_id` không dùng tới, nhưng phải có: logout không token là một request vô nghĩa,
    # và trả 204 cho nó sẽ làm client tưởng đã thu hồi được gì đó.
    user_id: CurrentUserId,
    # `session_token` chứ KHÔNG `bearer_token`: đây là chỗ thứ hai đọc token thô, và dùng
    # nhầm ở đây thì logout của web trả 204 mà không thu hồi gì — người dùng thấy màn đăng
    # nhập, còn phiên vẫn sống trên server tới 60 ngày.
    token: Annotated[str | None, Depends(session_token)],
    db: Db,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    service.logout(db, token)
    response = Response(status_code=204)
    clear_session_cookie(response, get_settings())
    return response
