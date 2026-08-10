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
from tests.conftest import OWNER_EMAIL, NguoiDungTest, sha256

REDIRECT = "https://testextensionid.chromiumapp.org/"


class GoogleGia:
    """Thay `GoogleTokenClient`. Ghi lại số lần bị gọi để khẳng định chốt chặn
    `redirect_uri` nằm TRƯỚC lượt gọi mạng."""

    def __init__(self) -> None:
        self.tra_ve: GoogleIdentity | None = None
        self.nem: Exception | None = None
        self.so_lan_goi = 0

    def exchange(self, code: str, redirect_uri: str) -> GoogleIdentity:
        self.so_lan_goi += 1
        if self.nem is not None:
            raise self.nem
        assert self.tra_ve is not None, "Test quên đặt danh tính trả về"
        return self.tra_ve


@pytest.fixture
def google(client: Any) -> Iterator[GoogleGia]:
    from app.auth.service import get_auth_service

    gia = GoogleGia()
    client.app.dependency_overrides[get_auth_service] = lambda: AuthService(google=gia)  # type: ignore[arg-type]
    yield gia
    client.app.dependency_overrides.pop(get_auth_service, None)


def _dang_nhap(client: Any, code: str, redirect_uri: str = REDIRECT) -> Any:
    return client.post(
        "/api/auth/google", json={"code": code, "redirectUri": redirect_uri}
    )


def _token_sau_dang_nhap(client: Any, code: str) -> str:
    resp = _dang_nhap(client, code)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["token"])


def _dem_user(db: Session) -> int:
    return int(db.execute(text("SELECT count(*) FROM app_user")).scalar_one())


def _owner_identity() -> GoogleIdentity:
    return GoogleIdentity(
        sub="sub-owner", email=OWNER_EMAIL, email_verified=True, name="Owner", picture=None
    )


def test_dang_nhap_lan_dau_bang_email_bootstrap_nhan_luon_so_tu_cu(
    client: Any, google: GoogleGia, db: Session, owner: NguoiDungTest
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
    truoc = _dem_user(db)
    google.tra_ve = _owner_identity()

    token = _token_sau_dang_nhap(client, "code-1")

    assert _dem_user(db) == truoc
    resp = client.get(
        "/api/vocab", params={"q": "legacyword"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["totalElements"] == 1


def test_google_sub_duoc_dien_vao_hang_cu(
    client: Any, google: GoogleGia, db: Session, owner: NguoiDungTest
) -> None:
    """Lần sau khớp theo sub, không theo email — vì email Google đổi được còn sub thì không."""
    google.tra_ve = _owner_identity()

    _token_sau_dang_nhap(client, "code-1")

    found = db.execute(
        text("SELECT count(*) FROM app_user WHERE google_sub = 'sub-owner'")
    ).scalar_one()
    assert found == 1


def test_email_chua_xac_minh_bi_tu_choi_va_khong_tao_tai_khoan(
    client: Any, google: GoogleGia, db: Session, owner: NguoiDungTest
) -> None:
    """`email_verified = false` nghĩa là Google KHÔNG bảo đảm người này sở hữu hộp thư đó,
    nên allowlist theo email mất sạch ý nghĩa."""
    truoc = _dem_user(db)
    google.tra_ve = GoogleIdentity(
        sub="sub-x", email="unverified@test.local", email_verified=False, name="X", picture=None
    )

    resp = _dang_nhap(client, "code-1")

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"
    assert resp.json()["retryable"] is False
    assert _dem_user(db) == truoc


def test_email_ngoai_allowlist_bi_tu_choi_403(
    client: Any, google: GoogleGia, db: Session, owner: NguoiDungTest
) -> None:
    """403 chứ không 401, và KHÔNG retry được: cần được cấp quyền là một hành động khác,
    không phải bấm lại."""
    truoc = _dem_user(db)
    google.tra_ve = GoogleIdentity(
        sub="sub-y", email="nguoila@test.local", email_verified=True, name="Y", picture=None
    )

    resp = _dang_nhap(client, "code-1")

    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"
    assert resp.json()["retryable"] is False
    assert _dem_user(db) == truoc


def test_redirect_uri_khong_khop_thi_khong_bao_gio_cham_google(
    client: Any, google: GoogleGia, owner: NguoiDungTest
) -> None:
    """Chốt chặn phải nằm TRƯỚC lượt gọi Google: nhận đại redirect_uri của client rồi
    chuyển cho Google là cho một extension lạ mượn client_secret của mình."""
    resp = _dang_nhap(client, "code-1", "https://ke-gian.chromiumapp.org/")

    assert resp.status_code == 401
    assert google.so_lan_goi == 0


def test_google_chet_thi_503_va_retry_duoc(
    client: Any, google: GoogleGia, owner: NguoiDungTest
) -> None:
    google.nem = AppError.of(ErrorCode.AUTH_UNAVAILABLE, "Google đang không phản hồi")

    resp = _dang_nhap(client, "code-1")

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUTH_UNAVAILABLE"
    assert resp.json()["retryable"] is True


def test_moi_lan_dang_nhap_tao_mot_phien_rieng(
    client: Any, google: GoogleGia, owner: NguoiDungTest
) -> None:
    """Đăng xuất máy này không đá máy kia ra."""
    google.tra_ve = _owner_identity()

    thu_nhat = _token_sau_dang_nhap(client, "code-1")
    thu_hai = _token_sau_dang_nhap(client, "code-2")
    assert thu_nhat != thu_hai

    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {thu_nhat}"})
    assert resp.status_code == 204

    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {thu_nhat}"}).status_code
        == 401
    )
    con_song = client.get("/api/auth/me", headers={"Authorization": f"Bearer {thu_hai}"})
    assert con_song.status_code == 200
    assert con_song.json()["email"] == OWNER_EMAIL


def test_token_tho_khong_bao_gio_duoc_luu_xuong_db(
    client: Any, google: GoogleGia, db: Session, owner: NguoiDungTest
) -> None:
    """Lộ bảng `user_session` không được phép cho ai mạo danh ai."""
    google.tra_ve = _owner_identity()

    token = _token_sau_dang_nhap(client, "code-1")

    tho = db.execute(
        text("SELECT count(*) FROM user_session WHERE token_hash = :t"), {"t": token}
    ).scalar_one()
    assert tho == 0
    bam = db.execute(
        text("SELECT count(*) FROM user_session WHERE token_hash = :t"), {"t": sha256(token)}
    ).scalar_one()
    assert bam == 1


def test_me_tra_dung_ho_so_nguoi_dang_nhap(client: Any, owner: NguoiDungTest) -> None:
    resp = client.get("/api/auth/me", headers=owner.headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == OWNER_EMAIL
    # Khoá luôn có mặt kể cả khi rỗng — mirror TypeScript khai `string | null`.
    assert set(body) == {"email", "displayName", "pictureUrl"}


def test_logout_khong_token_tra_401_chu_khong_204(client: Any) -> None:
    """Trả 204 cho request không token sẽ làm client tưởng đã thu hồi được gì đó."""
    assert client.post("/api/auth/logout").status_code == 401


def test_body_thieu_field_tra_400_dung_hinh_dang(client: Any) -> None:
    resp = client.post("/api/auth/google", json={"code": "x"})

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "INTERNAL"
    assert body["retryable"] is False
    assert "redirectUri" in body["message"] or "redirect_uri" in body["message"]
