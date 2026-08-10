"""POST /api/auth/google · GET /api/auth/me · POST /api/auth/logout"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.auth.deps import CurrentUserId, Db, bearer_token
from app.auth.models import AuthSessionDto, AuthUserDto, GoogleLoginRequest
from app.auth.service import AuthService, get_auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/google", response_model=AuthSessionDto)
def google(
    request: GoogleLoginRequest,
    db: Db,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionDto:
    """Công khai — đây là đường DUY NHẤT để có token, nên nó không thể đòi token."""
    return service.login(db, request.code, request.redirect_uri)


@router.get("/me", response_model=AuthUserDto)
def me(
    user_id: CurrentUserId,
    db: Db,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthUserDto:
    """Cách extension kiểm token còn sống sau khi Chrome khởi động lại, thay vì đợi một
    request nghiệp vụ nào đó nhận 401 rồi mới biết."""
    return service.me(db, user_id)


@router.post("/logout", status_code=204)
def logout(
    # `user_id` không dùng tới, nhưng phải có: logout không token là một request vô nghĩa,
    # và trả 204 cho nó sẽ làm client tưởng đã thu hồi được gì đó.
    user_id: CurrentUserId,
    token: Annotated[str | None, Depends(bearer_token)],
    db: Db,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    service.logout(db, token)
    return Response(status_code=204)
