"""Bản port của `AuthControllerIT` — đường đăng nhập.

`GoogleTokenClient` bị thay bằng hàng giả qua `dependency_overrides`, đúng lối
`@MockitoBean` bên Java. Giả lập ở tầng HTTP chỉ có chỗ trong `test_google_client.py`, nơi
thứ đang test chính là tầng đó.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.models import GoogleIdentity
from app.auth.service import AuthService
from app.common.errors import AppError, ErrorCode
from tests.conftest import OWNER_EMAIL, UserFixture, sha256

REDIRECT = "https://testextensionid.chromiumapp.org/"


class FakeGoogleClient:
    """Thay `GoogleTokenClient`. Ghi lại số lần bị gọi để khẳng định chốt chặn
    `redirect_uri` nằm TRƯỚC lượt gọi mạng."""

    def __init__(self) -> None:
        self.returns: GoogleIdentity | None = None
        self.error_to_raise: Exception | None = None
        self.call_count = 0

    def exchange(self, code: str, redirect_uri: str) -> GoogleIdentity:
        self.call_count += 1
        if self.error_to_raise is not None:
            raise self.error_to_raise
        assert self.returns is not None, "Test quên đặt danh tính trả về"
        return self.returns


@pytest.fixture
def google(client: Any) -> Iterator[FakeGoogleClient]:
    from app.auth.service import get_auth_service

    fake = FakeGoogleClient()
    client.app.dependency_overrides[get_auth_service] = lambda: AuthService(google=fake)  # type: ignore[arg-type]
    yield fake
    client.app.dependency_overrides.pop(get_auth_service, None)


def _login(client: Any, code: str, redirect_uri: str = REDIRECT) -> Any:
    return client.post(
        "/api/auth/google", json={"code": code, "redirectUri": redirect_uri}
    )


def _token_after_login(client: Any, code: str) -> str:
    resp = _login(client, code)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["token"])


def _count_users(db: Session) -> int:
    return int(db.execute(text("SELECT count(*) FROM app_user")).scalar_one())


def _owner_identity() -> GoogleIdentity:
    return GoogleIdentity(
        sub="sub-owner", email=OWNER_EMAIL, email_verified=True, name="Owner", picture=None
    )


def test_first_login_with_bootstrap_email_adopts_existing_vocab_book(
    client: Any, google: FakeGoogleClient, db: Session, owner: UserFixture
) -> None:
    """Hàng vocab cũ đã thuộc tài khoản do V6 tạo (google_sub còn NULL). Lần đăng nhập đầu
    phải NHẬN tài khoản đó chứ không tạo tài khoản thứ hai — nếu tạo, sổ từ cũ nằm ở tài
    khoản không ai vào được."""
    db.execute(
        text(
            "INSERT INTO vocab_entry (term, lang, pos, meaning_vi, user_id) "
            "VALUES ('legacyword', 'en', 'noun', 'từ cũ', :uid)"
        ),
        {"uid": owner.id},
    )
    db.commit()
    users_before = _count_users(db)
    google.returns = _owner_identity()

    token = _token_after_login(client, "code-1")

    assert _count_users(db) == users_before
    resp = client.get(
        "/api/vocab", params={"q": "legacyword"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["totalElements"] == 1


def test_google_sub_is_filled_into_the_existing_row(
    client: Any, google: FakeGoogleClient, db: Session, owner: UserFixture
) -> None:
    """Lần sau khớp theo sub, không theo email — vì email Google đổi được còn sub thì không."""
    google.returns = _owner_identity()

    _token_after_login(client, "code-1")

    found = db.execute(
        text("SELECT count(*) FROM app_user WHERE google_sub = 'sub-owner'")
    ).scalar_one()
    assert found == 1


def test_unverified_email_is_rejected_and_no_account_is_created(
    client: Any, google: FakeGoogleClient, db: Session, owner: UserFixture
) -> None:
    """`email_verified = false` nghĩa là Google KHÔNG bảo đảm người này sở hữu hộp thư đó,
    nên allowlist theo email mất sạch ý nghĩa."""
    users_before = _count_users(db)
    google.returns = GoogleIdentity(
        sub="sub-x", email="unverified@test.local", email_verified=False, name="X", picture=None
    )

    resp = _login(client, "code-1")

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"
    assert resp.json()["retryable"] is False
    assert _count_users(db) == users_before


def test_email_outside_allowlist_is_rejected_with_403(
    client: Any, google: FakeGoogleClient, db: Session, owner: UserFixture
) -> None:
    """403 chứ không 401, và KHÔNG retry được: cần được cấp quyền là một hành động khác,
    không phải bấm lại."""
    users_before = _count_users(db)
    google.returns = GoogleIdentity(
        sub="sub-y", email="nguoila@test.local", email_verified=True, name="Y", picture=None
    )

    resp = _login(client, "code-1")

    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"
    assert resp.json()["retryable"] is False
    assert _count_users(db) == users_before


def test_mismatched_redirect_uri_never_touches_google(
    client: Any, google: FakeGoogleClient, owner: UserFixture
) -> None:
    """Chốt chặn phải nằm TRƯỚC lượt gọi Google: nhận đại redirect_uri của client rồi
    chuyển cho Google là cho một extension lạ mượn client_secret của mình."""
    resp = _login(client, "code-1", "https://ke-gian.chromiumapp.org/")

    assert resp.status_code == 401
    assert google.call_count == 0


def test_google_down_returns_503_and_is_retryable(
    client: Any, google: FakeGoogleClient, owner: UserFixture
) -> None:
    google.error_to_raise = AppError.of(ErrorCode.AUTH_UNAVAILABLE, "Google đang không phản hồi")

    resp = _login(client, "code-1")

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUTH_UNAVAILABLE"
    assert resp.json()["retryable"] is True


def test_each_login_creates_a_separate_session(
    client: Any, google: FakeGoogleClient, owner: UserFixture
) -> None:
    """Đăng xuất máy này không đá máy kia ra."""
    google.returns = _owner_identity()

    first = _token_after_login(client, "code-1")
    second = _token_after_login(client, "code-2")
    assert first != second

    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {first}"})
    assert resp.status_code == 204

    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {first}"}).status_code
        == 401
    )
    alive_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {second}"})
    assert alive_response.status_code == 200
    assert alive_response.json()["email"] == OWNER_EMAIL


def test_raw_token_is_never_stored_in_the_db(
    client: Any, google: FakeGoogleClient, db: Session, owner: UserFixture
) -> None:
    """Lộ bảng `user_session` không được phép cho ai mạo danh ai."""
    google.returns = _owner_identity()

    token = _token_after_login(client, "code-1")

    raw_token_count = db.execute(
        text("SELECT count(*) FROM user_session WHERE token_hash = :t"), {"t": token}
    ).scalar_one()
    assert raw_token_count == 0
    hashed_count = db.execute(
        text("SELECT count(*) FROM user_session WHERE token_hash = :t"), {"t": sha256(token)}
    ).scalar_one()
    assert hashed_count == 1


def test_me_returns_the_correct_profile_of_the_logged_in_user(
    client: Any, owner: UserFixture
) -> None:
    resp = client.get("/api/auth/me", headers=owner.headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == OWNER_EMAIL
    # Khoá luôn có mặt kể cả khi rỗng — mirror TypeScript khai `string | null`.
    assert set(body) == {"email", "displayName", "pictureUrl"}


def test_logout_without_token_returns_401_not_204(client: Any) -> None:
    """Trả 204 cho request không token sẽ làm client tưởng đã thu hồi được gì đó."""
    assert client.post("/api/auth/logout").status_code == 401


def test_body_missing_field_returns_400_with_the_right_shape(client: Any) -> None:
    resp = client.post("/api/auth/google", json={"code": "x"})

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "INTERNAL"
    assert body["retryable"] is False
    assert "redirectUri" in body["message"] or "redirect_uri" in body["message"]
