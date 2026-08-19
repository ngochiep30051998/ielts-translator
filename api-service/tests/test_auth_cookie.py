"""Đường xác thực thứ hai: cookie phiên cho web app cùng origin.

Extension vẫn đi bằng header `Authorization` và không đổi gì. Ở đây kiểm đúng ba chuyện:
token đọc được từ cookie, header thắng khi có cả hai, và — quan trọng nhất — cookie KHÔNG
được chấp nhận nếu thiếu header `X-IELTS-Web`.

Chốt chặn cuối là điều kiện sống còn chứ không phải cho chặt: cookie là *ambient
credential*, nó tự đi kèm mọi request kể cả request do một trang lạ kích hoạt.
`SameSite=Lax` che POST/DELETE nhưng CỐ Ý cho GET điều hướng đi qua, mà repo có endpoint
GET gây tác dụng phụ thật — `GET /api/srs/due` commit DB và xếp tới 10 lượt gọi Gemini,
không qua quota guard. Header bắt buộc là thứ chặn đường đó: điều hướng top-level không đặt
được header, còn fetch cross-site mang header lạ thì vấp preflight mà CORS chỉ mở cho
`chrome-extension://`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.auth.cookies import session_cookie_name
from app.config import get_settings
from tests.conftest import UserFixture, create_user

WEB_HEADER = {"X-IELTS-Web": "1"}


def _set_cookie(client: Any, token: str) -> None:
    client.cookies.clear()
    client.cookies.set(session_cookie_name(get_settings()), token)


def test_cookie_with_web_header_identifies_the_user(
    client: Any, owner: UserFixture
) -> None:
    _set_cookie(client, owner.token)

    resp = client.get("/api/auth/me", headers=WEB_HEADER)

    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == owner.email


def test_cookie_missing_web_header_is_treated_as_not_logged_in(
    client: Any, owner: UserFixture
) -> None:
    """Đây là chốt chặn CSRF. Hỏng dòng này là mở toàn bộ API cho mọi trang trên Internet."""
    _set_cookie(client, owner.token)

    resp = client.get("/api/auth/me")

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_get_with_side_effects_cannot_be_triggered_by_navigation(
    client: Any, owner: UserFixture
) -> None:
    """`GET /api/srs/due` commit DB và xếp lượt gọi Gemini. Một điều hướng top-level từ
    trang lạ mang theo cookie nhưng KHÔNG mang được header — phải bị từ chối."""
    _set_cookie(client, owner.token)

    resp = client.get("/api/srs/due?limit=10&newLimit=5")

    assert resp.status_code == 401


def test_authorization_header_wins_when_both_are_present(
    client: Any, db: Session, owner: UserFixture
) -> None:
    other_user = create_user(db, "second@test.local")
    _set_cookie(client, other_user.token)

    resp = client.get("/api/auth/me", headers={**owner.headers, **WEB_HEADER})

    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == owner.email


def test_extension_does_not_need_the_web_header(client: Any, owner: UserFixture) -> None:
    """Đường Bearer miễn nhiễm CSRF theo thiết kế nên không chịu ràng buộc header."""
    client.cookies.clear()

    resp = client.get("/api/auth/me", headers=owner.headers)

    assert resp.status_code == 200, resp.text


def test_garbage_cookie_returns_401_not_500(client: Any) -> None:
    _set_cookie(client, "khong-phai-token-that")

    resp = client.get("/api/auth/me", headers=WEB_HEADER)

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_logout_by_cookie_really_revokes_the_session(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """`router.logout` lấy token qua dependency RIÊNG, không qua `optional_user_id`.

    Sửa mỗi chỗ đọc user mà quên chỗ này thì logout của web trả 204 mà không thu hồi gì —
    người dùng thấy màn đăng nhập, còn phiên vẫn sống 60 ngày trên server.
    """
    _set_cookie(client, owner.token)

    resp = client.post("/api/auth/logout", headers=WEB_HEADER)
    assert resp.status_code == 204, resp.text

    # Phiên phải chết THẬT, kiểm bằng chính token đó qua đường Bearer.
    client.cookies.clear()
    assert client.get("/api/auth/me", headers=owner.headers).status_code == 401


def test_logout_clears_the_cookie_in_the_browser(client: Any, owner: UserFixture) -> None:
    _set_cookie(client, owner.token)

    resp = client.post("/api/auth/logout", headers=WEB_HEADER)

    cookie_name = session_cookie_name(get_settings())
    assert cookie_name in resp.headers.get("set-cookie", ""), resp.headers.get("set-cookie")


def test_me_refreshes_the_cookie_expiry(client: Any, owner: UserFixture) -> None:
    """Hạn cookie và hạn phiên trong DB trượt theo hai đồng hồ khác nhau: DB gia hạn mỗi
    ngày dùng, còn Max-Age của cookie đóng băng lúc phát. Không phát lại thì người vào hàng
    ngày vẫn bị đá ra đúng ngày thứ 60."""
    _set_cookie(client, owner.token)

    resp = client.get("/api/auth/me", headers=WEB_HEADER)

    assert resp.status_code == 200
    assert session_cookie_name(get_settings()) in resp.headers.get("set-cookie", "")


def test_cookie_name_carries_the_host_prefix_when_secure(client: Any) -> None:
    """`__Host-` là thứ ngăn một subdomain ghi đè cookie của domain cha — cookie không có
    tính toàn vẹn theo origin. Trên `*.vercel.app` đó không phải rủi ro lý thuyết."""
    assert session_cookie_name(get_settings()).startswith("__Host-")
