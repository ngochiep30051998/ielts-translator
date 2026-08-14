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
from tests.conftest import NguoiDungTest, tao_nguoi_dung

WEB_HEADER = {"X-IELTS-Web": "1"}


def _dat_cookie(client: Any, token: str) -> None:
    client.cookies.clear()
    client.cookies.set(session_cookie_name(get_settings()), token)


def test_cookie_kem_header_web_thi_nhan_dien_duoc_nguoi_dung(
    client: Any, owner: NguoiDungTest
) -> None:
    _dat_cookie(client, owner.token)

    resp = client.get("/api/auth/me", headers=WEB_HEADER)

    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == owner.email


def test_cookie_thieu_header_web_thi_coi_nhu_chua_dang_nhap(
    client: Any, owner: NguoiDungTest
) -> None:
    """Đây là chốt chặn CSRF. Hỏng dòng này là mở toàn bộ API cho mọi trang trên Internet."""
    _dat_cookie(client, owner.token)

    resp = client.get("/api/auth/me")

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_get_co_tac_dung_phu_khong_kich_hoat_duoc_bang_dieu_huong(
    client: Any, owner: NguoiDungTest
) -> None:
    """`GET /api/srs/due` commit DB và xếp lượt gọi Gemini. Một điều hướng top-level từ
    trang lạ mang theo cookie nhưng KHÔNG mang được header — phải bị từ chối."""
    _dat_cookie(client, owner.token)

    resp = client.get("/api/srs/due?limit=10&newLimit=5")

    assert resp.status_code == 401


def test_header_authorization_thang_khi_co_ca_hai(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    nguoi_khac = tao_nguoi_dung(db, "second@test.local")
    _dat_cookie(client, nguoi_khac.token)

    resp = client.get("/api/auth/me", headers={**owner.headers, **WEB_HEADER})

    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == owner.email


def test_extension_khong_can_header_web(client: Any, owner: NguoiDungTest) -> None:
    """Đường Bearer miễn nhiễm CSRF theo thiết kế nên không chịu ràng buộc header."""
    client.cookies.clear()

    resp = client.get("/api/auth/me", headers=owner.headers)

    assert resp.status_code == 200, resp.text


def test_cookie_rac_tra_401_chu_khong_500(client: Any) -> None:
    _dat_cookie(client, "khong-phai-token-that")

    resp = client.get("/api/auth/me", headers=WEB_HEADER)

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_logout_bang_cookie_thu_hoi_that_phien(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`router.logout` lấy token qua dependency RIÊNG, không qua `optional_user_id`.

    Sửa mỗi chỗ đọc user mà quên chỗ này thì logout của web trả 204 mà không thu hồi gì —
    người dùng thấy màn đăng nhập, còn phiên vẫn sống 60 ngày trên server.
    """
    _dat_cookie(client, owner.token)

    resp = client.post("/api/auth/logout", headers=WEB_HEADER)
    assert resp.status_code == 204, resp.text

    # Phiên phải chết THẬT, kiểm bằng chính token đó qua đường Bearer.
    client.cookies.clear()
    assert client.get("/api/auth/me", headers=owner.headers).status_code == 401


def test_logout_xoa_cookie_o_trinh_duyet(client: Any, owner: NguoiDungTest) -> None:
    _dat_cookie(client, owner.token)

    resp = client.post("/api/auth/logout", headers=WEB_HEADER)

    ten = session_cookie_name(get_settings())
    assert ten in resp.headers.get("set-cookie", ""), resp.headers.get("set-cookie")


def test_me_lam_moi_han_cookie(client: Any, owner: NguoiDungTest) -> None:
    """Hạn cookie và hạn phiên trong DB trượt theo hai đồng hồ khác nhau: DB gia hạn mỗi
    ngày dùng, còn Max-Age của cookie đóng băng lúc phát. Không phát lại thì người vào hàng
    ngày vẫn bị đá ra đúng ngày thứ 60."""
    _dat_cookie(client, owner.token)

    resp = client.get("/api/auth/me", headers=WEB_HEADER)

    assert resp.status_code == 200
    assert session_cookie_name(get_settings()) in resp.headers.get("set-cookie", "")


def test_ten_cookie_mang_tien_to_host_khi_secure(client: Any) -> None:
    """`__Host-` là thứ ngăn một subdomain ghi đè cookie của domain cha — cookie không có
    tính toàn vẹn theo origin. Trên `*.vercel.app` đó không phải rủi ro lý thuyết."""
    assert session_cookie_name(get_settings()).startswith("__Host-")
