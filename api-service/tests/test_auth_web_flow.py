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


class GoogleGia:
    """Thay `GoogleTokenClient`. Đếm số lần bị gọi để chứng minh chốt chặn state nằm TRƯỚC
    lượt gọi mạng."""

    def __init__(self) -> None:
        self.tra_ve: GoogleIdentity | None = None
        self.so_lan_goi = 0
        self.redirect_uri_nhan_duoc: str | None = None

    def exchange(self, code: str, redirect_uri: str) -> GoogleIdentity:
        self.so_lan_goi += 1
        self.redirect_uri_nhan_duoc = redirect_uri
        assert self.tra_ve is not None, "Test quên đặt danh tính trả về"
        return self.tra_ve


@pytest.fixture
def google(client: Any) -> Iterator[GoogleGia]:
    from app.auth.service import get_auth_service

    gia = GoogleGia()
    client.app.dependency_overrides[get_auth_service] = lambda: AuthService(google=gia)  # type: ignore[arg-type]
    yield gia
    client.app.dependency_overrides.pop(get_auth_service, None)


def _danh_tinh(email: str = OWNER_EMAIL, verified: bool = True) -> GoogleIdentity:
    return GoogleIdentity(
        sub=f"sub-{email}", email=email, email_verified=verified, name="A", picture=None
    )


def _start(client: Any) -> Any:
    return client.get("/api/auth/google/start", follow_redirects=False)


def _state_dang_giu(client: Any) -> str:
    return client.cookies[state_cookie_name(get_settings())]


def _callback(client: Any, **params: str) -> Any:
    return client.get("/api/auth/google/callback", params=params, follow_redirects=False)


def _auth_error(resp: Any) -> str | None:
    return parse_qs(urlparse(resp.headers["location"]).query).get("authError", [None])[0]


# ── /start ───────────────────────────────────────────────────────────────────


def test_start_chuyen_huong_sang_google_kem_state(client: Any) -> None:
    resp = _start(client)

    assert resp.status_code == 302
    dich = urlparse(resp.headers["location"])
    assert dich.netloc == "accounts.google.com"

    q = parse_qs(dich.query)
    assert q["response_type"] == ["code"]
    assert q["prompt"] == ["select_account"]
    assert q["state"][0]
    # `openid` thiếu là hỏng CÂM: Google vẫn trả 200 nhưng không có id_token, và lỗi hiện ra
    # như thể phía Google sai.
    assert "openid" in q["scope"][0]
    assert q["redirect_uri"] == [get_settings().web_redirect_uri]


def test_start_phat_cookie_state_httponly_samesite_lax(client: Any) -> None:
    resp = _start(client)

    set_cookie = resp.headers["set-cookie"]
    assert state_cookie_name(get_settings()) in set_cookie
    assert "HttpOnly" in set_cookie
    # Lax chứ KHÔNG Strict: redirect từ accounts.google.com về callback là điều hướng
    # cross-site, Strict sẽ không gửi cookie và 100% lượt đăng nhập hỏng.
    assert "samesite=lax" in set_cookie.lower()
    assert "Secure" in set_cookie


def test_state_moi_lan_mot_khac(client: Any) -> None:
    _start(client)
    dau = _state_dang_giu(client)
    _start(client)

    assert _state_dang_giu(client) != dau


# ── /callback: các đường từ chối ─────────────────────────────────────────────


def test_callback_khong_co_state_thi_tu_choi_va_khong_cham_google(
    client: Any, google: GoogleGia
) -> None:
    resp = _callback(client, code="c")

    assert resp.status_code == 302
    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.so_lan_goi == 0


def test_callback_state_rong_ca_hai_ben_van_bi_tu_choi(
    client: Any, google: GoogleGia
) -> None:
    """Bẫy `None == None`: viết `if state != cookie` trần thì cả hai cùng vắng sẽ CHO QUA."""
    client.cookies.clear()

    resp = _callback(client, code="c", state="")

    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.so_lan_goi == 0


def test_callback_state_khong_khop_thi_tu_choi(client: Any, google: GoogleGia) -> None:
    _start(client)

    resp = _callback(client, code="c", state="state-cua-ke-khac")

    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.so_lan_goi == 0


def test_callback_state_ngoai_ascii_tra_302_chu_khong_500(
    client: Any, google: GoogleGia
) -> None:
    """`secrets.compare_digest` ném TypeError với non-ASCII, mà state do client điều khiển
    hoàn toàn. Không chặn trước thì `?state=é` biến 401 thành 500."""
    _start(client)

    resp = _callback(client, code="c", state="é")

    assert resp.status_code == 302
    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.so_lan_goi == 0


def test_callback_google_tra_error_thi_ve_nha_kem_ma_loi(
    client: Any, google: GoogleGia
) -> None:
    _start(client)

    resp = _callback(client, error="access_denied", state=_state_dang_giu(client))

    assert _auth_error(resp) == "UNAUTHORIZED"
    assert google.so_lan_goi == 0


def test_callback_email_ngoai_allowlist_tra_ma_FORBIDDEN(
    client: Any, google: GoogleGia
) -> None:
    """FORBIDDEN phải phân biệt được với UNAUTHORIZED: một bên bấm lại là xong, bên kia phải
    nhờ quản trị thêm email. Trộn hai mã là chỉ sai đường hồi phục."""
    google.tra_ve = _danh_tinh("nguoi-la@test.local")
    _start(client)

    resp = _callback(client, code="c", state=_state_dang_giu(client))

    assert _auth_error(resp) == "FORBIDDEN"


def test_callback_email_chua_xac_minh_bi_tu_choi(client: Any, google: GoogleGia) -> None:
    google.tra_ve = _danh_tinh(verified=False)
    _start(client)

    resp = _callback(client, code="c", state=_state_dang_giu(client))

    assert _auth_error(resp) == "UNAUTHORIZED"


# ── /callback: đường thành công ──────────────────────────────────────────────


def test_callback_thanh_cong_phat_cookie_phien_va_ve_trang_chu(
    client: Any, google: GoogleGia
) -> None:
    google.tra_ve = _danh_tinh()
    _start(client)

    resp = _callback(client, code="c", state=_state_dang_giu(client))

    assert resp.status_code == 302
    assert resp.headers["location"] == "/"

    cookies = resp.headers.get_list("set-cookie")
    phien = next(c for c in cookies if c.startswith(session_cookie_name(get_settings())))
    assert "HttpOnly" in phien
    assert "Secure" in phien
    assert "samesite=lax" in phien.lower()
    assert "Path=/" in phien
    # `__Host-` cấm thuộc tính Domain — có nó là mất luôn tính toàn vẹn theo origin.
    assert "Domain=" not in phien


def test_callback_dung_redirect_uri_dung_tu_config_khong_tu_client(
    client: Any, google: GoogleGia
) -> None:
    google.tra_ve = _danh_tinh()
    _start(client)

    _callback(client, code="c", state=_state_dang_giu(client))

    assert google.redirect_uri_nhan_duoc == get_settings().web_redirect_uri


def test_sau_callback_thi_goi_duoc_api_bang_cookie(
    client: Any, google: GoogleGia, db: Session
) -> None:
    """Đường đi trọn vẹn: đăng nhập bằng điều hướng, rồi dùng app bằng cookie."""
    google.tra_ve = _danh_tinh()
    _start(client)
    _callback(client, code="c", state=_state_dang_giu(client))

    resp = client.get("/api/auth/me", headers={"X-IELTS-Web": "1"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == OWNER_EMAIL


def test_redirect_uri_cua_web_KHONG_dung_duoc_cho_luong_extension(
    client: Any, google: GoogleGia
) -> None:
    """Hai luồng KHÔNG được mượn redirect_uri của nhau.

    `POST /api/auth/google` trả token phiên THÔ trong JSON body. Nếu nó chấp nhận luôn
    redirect_uri của web callback thì luồng cookie httpOnly — vốn cố ý giấu token khỏi
    JavaScript — bỗng có một đường vòng để đọc chính token đó.
    """
    google.tra_ve = _danh_tinh()

    resp = client.post(
        "/api/auth/google",
        json={"code": "c", "redirectUri": get_settings().web_redirect_uri},
    )

    assert resp.status_code == 401
    assert google.so_lan_goi == 0
