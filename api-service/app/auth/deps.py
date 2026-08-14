"""Nhận diện người dùng của request — bản thay `SessionFilter` + `AuthContext`.

Sạch hơn hẳn bản Java. Bên đó phải có một bean `@RequestScope` vì Tomcat tái dùng thread và
một ThreadLocal quên dọn là request sau đọc nhầm user của request trước — rò dữ liệu giữa
hai người, im lặng. Ở FastAPI, user được truyền vào handler như một tham số, nên không tồn
tại trạng thái nào để rò.

Giữ nguyên một điểm quan trọng của bản Java: **việc bắt buộc đăng nhập nằm ở dependency của
từng route, không nằm ở middleware**. Lỗi ném từ middleware chạy ngoài phạm vi exception
handler và sẽ mất hình dạng `{code, message, retryable}` mà toàn bộ UI đang dựa vào.

Có ĐÚNG HAI đường mang danh tính, và chúng không đối xứng:

- **Header `Authorization: Bearer`** — extension. Miễn nhiễm CSRF theo thiết kế: không trang
  nào đặt được header đó thay người dùng.
- **Cookie phiên** — web app cùng origin. Là *ambient credential*, nên phải có chốt chặn
  riêng; xem `session_token`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.auth.cookies import WEB_CLIENT_HEADER, session_cookie_name
from app.auth.service import AuthService, get_auth_service
from app.common.errors import AppError, ErrorCode
from app.config import get_settings
from app.db import get_db

BEARER = "Bearer "


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str | None:
    """Token thô trong header `Authorization: Bearer <token>`, hoặc None."""
    if authorization is None or not authorization.startswith(BEARER):
        return None
    token = authorization[len(BEARER) :].strip()
    return token or None


def cookie_token(request: Request) -> str | None:
    """Token phiên từ cookie — CHỈ khi request mang header `X-IELTS-Web`.

    **Header là chốt chặn CSRF, không phải một chi tiết cho gọn.** Cookie tự đi kèm mọi
    request, kể cả request do một trang lạ kích hoạt. `SameSite=Lax` che POST/DELETE nhưng
    CỐ Ý cho GET điều hướng đi qua, và repo có endpoint GET gây tác dụng phụ thật:
    `GET /api/srs/due` và `/api/srs/practice` commit DB rồi xếp tới 10 lượt gọi Gemini —
    và đường đó KHÔNG qua quota guard.

    Điều hướng top-level không đặt được header. Fetch cross-site mang header lạ thì vấp
    preflight, mà CORS chỉ mở cho `chrome-extension://<id>`. Nên một header bắt buộc là chốt
    chặn đầy đủ, không phụ thuộc trình duyệt, và không cần mã lỗi mới: thiếu nó thì đơn giản
    là không nhận diện được ai — y như chưa đăng nhập.

    Đọc tên cookie qua `get_settings()` chứ không khai thành tham số tĩnh: tên phụ thuộc cờ
    Secure, vì `__Host-` cấm cookie không-Secure.
    """
    if not request.headers.get(WEB_CLIENT_HEADER):
        return None
    token = request.cookies.get(session_cookie_name(get_settings()))
    return token.strip() if token and token.strip() else None


def session_token(
    header_token: Annotated[str | None, Depends(bearer_token)],
    cookie: Annotated[str | None, Depends(cookie_token)],
) -> str | None:
    """Token phiên của request, bất kể nó tới bằng đường nào.

    Header thắng khi có cả hai — một máy vừa cài extension vừa mở web app là chuyện thường,
    và request do extension phát ra phải mang danh tính của extension.

    PHẢI dùng ở MỌI chỗ cần token thô. `logout` ở `router.py` là chỗ thứ hai (ngoài
    `optional_user_id`): chỉ sửa một chỗ thì logout của web trả 204 mà không thu hồi gì —
    người dùng thấy màn đăng nhập, còn phiên vẫn sống trên server tới 60 ngày.
    """
    return header_token or cookie


def optional_user_id(
    token: Annotated[str | None, Depends(session_token)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> int | None:
    """None khi chưa đăng nhập. Chỉ dùng cho chỗ THẬT SỰ cho phép ẩn danh.

    Token rác không ném: nó chỉ đơn giản là không nhận diện được ai.
    """
    return service.resolve_user_id(db, token)


def current_user_id(user_id: Annotated[int | None, Depends(optional_user_id)]) -> int:
    """Id của người đang đăng nhập. Ném UNAUTHORIZED nếu chưa có.

    Đây là bản dịch của `AuthContext.requireUserId()`. Mọi endpoint chạm dữ liệu học PHẢI
    lấy `user_id` qua đây và lọc theo nó (ràng buộc #13) — id nhận từ client luôn tra theo
    `(id, user_id)`.
    """
    if user_id is None:
        raise AppError.of(ErrorCode.UNAUTHORIZED, "Cần đăng nhập để dùng chức năng này")
    return user_id


CurrentUserId = Annotated[int, Depends(current_user_id)]
Db = Annotated[Session, Depends(get_db)]
