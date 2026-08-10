"""Entity và DTO của context auth.

Entity ánh xạ đúng DDL của `V6__auth.sql` + `V7__session_token_hash_varchar.sql`. Schema
THẬT do migration dựng; các khai báo ở đây phải khớp nó, không phải sinh ra nó — vai trò
giống `ddl-auto: validate` bên Java.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.schema import ApiModel
from app.db import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    #: NULL với hàng do V6 tạo ra và chưa ai đăng nhập. Lần đăng nhập đầu khớp theo EMAIL
    #: rồi điền cột này; từ đó về sau khớp theo sub, vì email Google đổi được còn sub thì
    #: không.
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    picture_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    """Một phiên đăng nhập trên một thiết bị.

    Đăng nhập ở máy thứ hai tạo hàng mới chứ không ghi đè — đó là lý do đăng xuất ở máy này
    không đá máy kia ra.
    """

    __tablename__ = "user_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    #: SHA-256 hex của token. Bản gốc chỉ tồn tại đúng một lần, trong response đăng nhập.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[AppUser] = relationship(lazy="joined")


class GoogleLoginRequest(ApiModel):
    """`redirectUri` gửi lên để backend SO SÁNH, không phải để backend dùng theo. Giá trị
    thật luôn được dựng lại từ EXTENSION_ID phía server."""

    code: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)


class AuthUserDto(ApiModel):
    email: str
    display_name: str | None = None
    picture_url: str | None = None


class AuthSessionDto(ApiModel):
    """`token` là bản GỐC của token phiên. Đây là lần duy nhất nó tồn tại ngoài thiết bị
    người dùng — DB chỉ giữ SHA-256 của nó."""

    token: str
    expires_at: datetime
    user: AuthUserDto


class GoogleIdentity(ApiModel):
    """Danh tính lấy được từ Google. Chỉ những claim thực sự dùng tới."""

    sub: str
    email: str
    email_verified: bool
    name: str | None = None
    picture: str | None = None
