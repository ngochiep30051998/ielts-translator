"""Nghiệp vụ đăng nhập / nhận diện phiên — bản port của `AuthService`."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.auth import repository as repo
from app.auth.google import GoogleTokenClient, get_google_client
from app.auth.models import AppUser, AuthSessionDto, AuthUserDto, GoogleIdentity, UserSession
from app.common.errors import AppError, ErrorCode
from app.config import Settings, get_settings

TOKEN_BYTES = 32

#: Hạn phiên trượt theo mỗi lần dùng, nhưng chỉ GHI LẠI tối đa một lần mỗi ngày.
#:
#: Không có ngưỡng này thì mọi request đều kéo theo một lượt UPDATE, biến bảng phiên thành
#: điểm nóng vì đúng một lý do làm đẹp.
TOUCH_INTERVAL = timedelta(days=1)


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_token() -> str:
    """32 byte ngẫu nhiên. Bản gốc trả cho client, DB chỉ giữ hash.

    base64url không đệm, khớp `Base64.getUrlEncoder().withoutPadding()` bên Java — token cũ
    do backend Spring phát ra vẫn dùng được sau khi cắt sang, vì cả hai chỉ so hash.
    """
    return base64.urlsafe_b64encode(secrets.token_bytes(TOKEN_BYTES)).decode("ascii").rstrip("=")


def _now() -> datetime:
    return datetime.now(UTC)


class AuthService:
    def __init__(
        self, google: GoogleTokenClient | None = None, settings: Settings | None = None
    ) -> None:
        self._google = google or get_google_client()
        self._settings = settings or get_settings()

    def extension_redirect_uri(self) -> str:
        """Dựng từ EXTENSION_ID phía server, KHÔNG nhận từ client."""
        return f"https://{self._settings.extension_id}.chromiumapp.org/"

    def web_redirect_uri(self) -> str:
        """Dựng từ WEB_BASE_URL phía server, KHÔNG nhận từ client và KHÔNG lấy từ
        `request.base_url` — cái sau đọc header `Host`, tức Host header injection."""
        return self._settings.web_redirect_uri

    def _allowed(self, email: str) -> bool:
        """Danh sách rỗng = KHÓA HẾT, cố ý. Cấu hình thiếu phải làm hệ thống đóng lại chứ
        không mở toang cho mọi tài khoản Google trên đời."""
        allowed = self._settings.allowed_email_set
        if not allowed:
            return False
        return email.strip().lower() in allowed

    def login(self, db: Session, code: str, redirect_uri: str) -> AuthSessionDto:
        """Luồng EXTENSION. Chấp nhận đúng một redirect_uri: cái dựng từ EXTENSION_ID.

        **Không nới thành "một trong hai".** Endpoint này trả token phiên THÔ trong JSON
        body; nếu nó chấp nhận luôn redirect_uri của web callback thì hai luồng mượn được
        của nhau, và luồng có cookie httpOnly (vốn cố ý giấu token khỏi JavaScript) bỗng có
        một đường vòng để đọc chính token đó.
        """
        # Chốt chặn redirect_uri nằm TRƯỚC khi chạm mạng: nhận đại chuỗi client gửi rồi
        # chuyển cho Google là cho một extension lạ mượn client_secret của mình.
        if self.extension_redirect_uri() != redirect_uri:
            raise AppError.of(ErrorCode.UNAUTHORIZED, "redirect_uri không hợp lệ")
        return self._finish_login(db, code, redirect_uri)

    def login_web(self, db: Session, code: str) -> AuthSessionDto:
        """Luồng WEB. Không có gate so chuỗi vì không có chuỗi nào đến từ client — redirect
        uri dựng thẳng từ config ngay tại đây."""
        return self._finish_login(db, code, self.web_redirect_uri())

    def _finish_login(self, db: Session, code: str, redirect_uri: str) -> AuthSessionDto:
        """Phần chung sau khi đã chốt được redirect_uri: đổi code, kiểm quyền, mở phiên."""
        identity = self._google.exchange(code, redirect_uri)

        # email_verified = false nghĩa là Google KHÔNG bảo đảm người này sở hữu hộp thư đó,
        # nên allowlist theo email mất sạch ý nghĩa.
        if not identity.email_verified:
            raise AppError.of(ErrorCode.UNAUTHORIZED, "Email này chưa được Google xác minh")
        if not self._allowed(identity.email):
            raise AppError.of(
                ErrorCode.FORBIDDEN, "Tài khoản này chưa được cấp quyền dùng hệ thống"
            )

        user = self._resolve_user(db, identity)
        raw_token = _new_token()
        now = _now()
        session = UserSession(
            user_id=user.id,
            token_hash=_sha256(raw_token),
            last_used_at=now,
            expires_at=now + timedelta(days=self._settings.auth_session_days),
        )
        db.add(session)
        db.flush()

        return AuthSessionDto(token=raw_token, expires_at=session.expires_at, user=_to_dto(user))

    @staticmethod
    def _resolve_user(db: Session, identity: GoogleIdentity) -> AppUser:
        """Khớp theo google_sub trước; không có thì theo email — đó là ca hàng do V6 tạo ra
        và chưa ai đăng nhập, và cũng là lúc sổ từ cũ được nhận chủ."""
        user = repo.find_by_google_sub(db, identity.sub) or repo.find_by_email_ignore_case(
            db, identity.email
        )
        if user is None:
            user = AppUser(email=identity.email)
            db.add(user)

        user.google_sub = identity.sub
        user.email = identity.email
        if identity.name is not None:
            user.display_name = identity.name
        if identity.picture is not None:
            user.picture_url = identity.picture
        user.last_login_at = _now()
        db.flush()
        return user

    def resolve_user_id(self, db: Session, raw_token: str | None) -> int | None:
        """Nhận diện user từ token. Trả None cho mọi ca hỏng — token rác, hết hạn, đã thu
        hồi đều không phân biệt được với nhau từ phía người gọi, và cũng không nên."""
        if raw_token is None or not raw_token.strip():
            return None
        now = _now()
        session = repo.find_alive_session(db, _sha256(raw_token), now)
        if session is None:
            return None
        if session.last_used_at < now - TOUCH_INTERVAL:
            session.last_used_at = now
            session.expires_at = now + timedelta(days=self._settings.auth_session_days)
            db.flush()
        return session.user_id

    def logout(self, db: Session, raw_token: str | None) -> None:
        """Thu hồi ĐÚNG phiên đang dùng. Các thiết bị khác không bị đá ra."""
        if raw_token is None or not raw_token.strip():
            return
        now = _now()
        session = repo.find_alive_session(db, _sha256(raw_token), now)
        if session is not None:
            session.revoked_at = now
            db.flush()

    @staticmethod
    def me(db: Session, user_id: int) -> AuthUserDto:
        user = repo.find_user_by_id(db, user_id)
        if user is None:
            raise AppError.of(ErrorCode.UNAUTHORIZED, "Phiên không còn hợp lệ")
        return _to_dto(user)


def _to_dto(user: AppUser) -> AuthUserDto:
    return AuthUserDto(
        email=user.email, display_name=user.display_name, picture_url=user.picture_url
    )


def get_auth_service() -> AuthService:
    return AuthService()
