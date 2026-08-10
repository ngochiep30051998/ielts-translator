"""Nhận diện người dùng của request — bản thay `SessionFilter` + `AuthContext`.

Sạch hơn hẳn bản Java. Bên đó phải có một bean `@RequestScope` vì Tomcat tái dùng thread và
một ThreadLocal quên dọn là request sau đọc nhầm user của request trước — rò dữ liệu giữa
hai người, im lặng. Ở FastAPI, user được truyền vào handler như một tham số, nên không tồn
tại trạng thái nào để rò.

Giữ nguyên một điểm quan trọng của bản Java: **việc bắt buộc đăng nhập nằm ở dependency của
từng route, không nằm ở middleware**. Lỗi ném từ middleware chạy ngoài phạm vi exception
handler và sẽ mất hình dạng `{code, message, retryable}` mà toàn bộ UI đang dựa vào.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.auth.service import AuthService, get_auth_service
from app.common.errors import AppError, ErrorCode
from app.db import get_db

BEARER = "Bearer "


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str | None:
    """Token thô trong header `Authorization: Bearer <token>`, hoặc None."""
    if authorization is None or not authorization.startswith(BEARER):
        return None
    token = authorization[len(BEARER) :].strip()
    return token or None


def optional_user_id(
    token: Annotated[str | None, Depends(bearer_token)],
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
