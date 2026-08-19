"""Luồng đăng nhập của web app: `/api/auth/google/start` → Google → `/api/auth/google/callback`.

Khác hẳn luồng extension ở một điểm quyết định mọi thứ còn lại: người dùng đang ở giữa một
lượt ĐIỀU HƯỚNG TRÌNH DUYỆT. Token không đi qua body được, và lỗi cũng không trả JSON được.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy.orm import Session

from app.auth.cookies import session_cookie_name, state_cookie_name
from app.auth.models import GoogleIdentity
from app.auth.service import AuthService
from app.config import get_settings
from tests.conftest import OWNER_EMAIL


class FakeGoogleTokenClient:
    """Thay `GoogleTokenClient`. Đếm số lần bị gọi để chứng minh chốt chặn state nằm TRƯỚC
    lượt gọi mạng."""

    def __init__(self) -> None:
        self.identity_to_return: GoogleIdentity | None = None
        self.call_count = 0
        self.received_redirect_uri: str | None = None

    def exchange(self, code: str, redirect_uri: str) -> GoogleIdentity:
        self.call_count += 1
        self.received_redirect_uri = redirect_uri
        assert self.identity_to_return is not None, "Test quên đặt danh tính trả về"
        return self.identity_to_return


@pytest.fixture
def google(client: Any) -> Iterator[FakeGoogleTokenClient]:
    from app.auth.service import get_auth_service

    fake = FakeGoogleTokenClient()
    client.app.dependency_overrides[get_auth_service] = lambda: AuthService(google=fake)  # type: ignore[arg-type]
    yield fake
    client.app.dependency_overrides.pop(get_auth_service, None)


def _identity(email: str = OWNER_EMAIL, verified: bool = True) -> GoogleIdentity:
    return GoogleIdentity(
        sub=f"sub-{email}", email=email, email_verified=verified, name="A", picture=None
    )


def _start(client: Any) -> Any:
    return client.get("/api/auth/google/start", follow_redirects=False)


def _held_state(client: Any) -> str:
    return client.cookies[state_cookie_name(get_settings())]


def _callback(client: Any, **params: str) -> Any:
    return client.get("/api/auth/google/callback", params=params, follow_redirects=False)


def _auth_error(resp: Any) -> str | None:
    return parse_qs(urlparse(resp.headers["location"]).query).get("authError", [None])[0]


# ── /start ───────────────────────────────────────────────────────────────────


def test_start_redirects_to_google_with_state(client: Any) -> None:
    resp = _start(client)

    assert resp.status_code == 302
    destination = urlparse(resp.headers["location"])
    assert destination.netloc == "accounts.google.com"

    q = parse_qs(destination.query)
    assert q["response_type"] == ["code"]
    assert q["prompt"] == ["select_account"]
    assert q["state"][0]
    # `openid` thiếu là hỏng CÂM: Google vẫn trả 200 nhưng không có id_token, và lỗi hiện ra
    # như thể phía Google sai.
    assert "openid" in q["scope"][0]
    assert q["redirect_uri"] == [get_settings().web_redirect_uri]


def test_start_issues_state_cookie_httponly_samesite_lax(client: Any) -> None:
    resp = _start(client)

    set_cookie = resp.headers["set-cookie"]
    assert state_cookie_name(get_settings()) in set_cookie
    assert "HttpOnly" in set_cookie
    # Lax chứ KHÔNG Strict: redirect từ accounts.google.com về callback là điều hướng
    # cross-site, Strict sẽ không gửi cookie và 100% lượt đăng nhập hỏng.
    assert "samesite=lax" in set_cookie.lower()
    assert "Secure" in set_cookie


def test_state_differs_on_every_start(client: Any) -> None:
    _start(client)
    first_state = _held_state(client)
    _start(client)

    assert _held_state(client) != first_state


# ── /callback: các đường từ chối ─────────────────────────────────────────────


def test_callback_without_state_is_rejected_and_does_not_touch_google(
    client: Any, google: FakeGoogleTokenClient
) -> None:
    resp = _callback(client, code="c")

    assert resp.status_code == 302
    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.call_count == 0


def test_callback_empty_state_on_both_sides_is_still_rejected(
    client: Any, google: FakeGoogleTokenClient
) -> None:
    """Bẫy `None == None`: viết `if state != cookie` trần thì cả hai cùng vắng sẽ CHO QUA."""
    client.cookies.clear()

    resp = _callback(client, code="c", state="")

    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.call_count == 0


def test_callback_mismatched_state_is_rejected(client: Any, google: FakeGoogleTokenClient) -> None:
    _start(client)

    resp = _callback(client, code="c", state="state-cua-ke-khac")

    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.call_count == 0


def test_callback_non_ascii_state_returns_302_not_500(
    client: Any, google: FakeGoogleTokenClient
) -> None:
    """`secrets.compare_digest` ném TypeError với non-ASCII, mà state do client điều khiển
    hoàn toàn. Không chặn trước thì `?state=é` biến 401 thành 500."""
    _start(client)

    resp = _callback(client, code="c", state="é")

    assert resp.status_code == 302
    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.call_count == 0


def test_callback_google_returns_error_then_redirects_home_with_error_code(
    client: Any, google: FakeGoogleTokenClient
) -> None:
    _start(client)

    resp = _callback(client, error="access_denied", state=_held_state(client))

    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.call_count == 0


def test_callback_email_outside_allowlist_returns_FORBIDDEN_code(
    client: Any, google: FakeGoogleTokenClient
) -> None:
    """FORBIDDEN phải phân biệt được với UNAUTHORIZED: một bên bấm lại là xong, bên kia phải
    nhờ quản trị thêm email. Trộn hai mã là chỉ sai đường hồi phục."""
    google.identity_to_return = _identity("nguoi-la@test.local")
    _start(client)

    resp = _callback(client, code="c", state=_held_state(client))

    assert _auth_error(resp) == "FORBIDDEN"


def test_callback_unverified_email_is_rejected(client: Any, google: FakeGoogleTokenClient) -> None:
    google.identity_to_return = _identity(verified=False)
    _start(client)

    resp = _callback(client, code="c", state=_held_state(client))

    assert _auth_error(resp) == "UNAUTHORIZED"


# ── /callback: đường thành công ──────────────────────────────────────────────


def test_callback_success_issues_session_cookie_and_redirects_to_home(
    client: Any, google: FakeGoogleTokenClient
) -> None:
    google.identity_to_return = _identity()
    _start(client)

    resp = _callback(client, code="c", state=_held_state(client))

    assert resp.status_code == 302
    assert resp.headers["location"] == "/"

    cookies = resp.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith(session_cookie_name(get_settings())))
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "samesite=lax" in session_cookie.lower()
    assert "Path=/" in session_cookie
    # `__Host-` cấm thuộc tính Domain — có nó là mất luôn tính toàn vẹn theo origin.
    assert "Domain=" not in session_cookie


def test_callback_uses_redirect_uri_from_config_not_from_client(
    client: Any, google: FakeGoogleTokenClient
) -> None:
    google.identity_to_return = _identity()
    _start(client)

    _callback(client, code="c", state=_held_state(client))

    assert google.received_redirect_uri == get_settings().web_redirect_uri


def test_after_callback_api_can_be_called_with_cookie(
    client: Any, google: FakeGoogleTokenClient, db: Session
) -> None:
    """Đường đi trọn vẹn: đăng nhập bằng điều hướng, rồi dùng app bằng cookie."""
    google.identity_to_return = _identity()
    _start(client)
    _callback(client, code="c", state=_held_state(client))

    resp = client.get("/api/auth/me", headers={"X-IELTS-Web": "1"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == OWNER_EMAIL


def test_web_redirect_uri_CANNOT_be_used_for_extension_flow(
    client: Any, google: FakeGoogleTokenClient
) -> None:
    """Hai luồng KHÔNG được mượn redirect_uri của nhau.

    `POST /api/auth/google` trả token phiên THÔ trong JSON body. Nếu nó chấp nhận luôn
    redirect_uri của web callback thì luồng cookie httpOnly — vốn cố ý giấu token khỏi
    JavaScript — bỗng có một đường vòng để đọc chính token đó.
    """
    google.identity_to_return = _identity()

    resp = client.post(
        "/api/auth/google",
        json={"code": "c", "redirectUri": get_settings().web_redirect_uri},
    )

    assert resp.status_code == 401
    assert google.call_count == 0
