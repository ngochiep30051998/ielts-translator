"""Truy vấn của context auth. Mọi câu chạm `app_user` / `user_session` nằm ở đây."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import AppUser, UserSession


def find_by_google_sub(db: Session, google_sub: str) -> AppUser | None:
    return db.scalars(select(AppUser).where(AppUser.google_sub == google_sub)).first()


def find_by_email_ignore_case(db: Session, email: str) -> AppUser | None:
    """Bỏ qua hoa thường là BẮT BUỘC, không phải chiều lòng.

    Google trả email chữ thường, nhưng AUTH_BOOTSTRAP_EMAIL do người gõ tay vào `.env` thì
    không chắc. Lệch hoa thường = tạo tài khoản thứ hai, và toàn bộ sổ từ cũ nằm ở tài khoản
    không ai đăng nhập được.
    """
    return db.scalars(
        select(AppUser).where(func.lower(AppUser.email) == email.strip().lower())
    ).first()


def find_user_by_id(db: Session, user_id: int) -> AppUser | None:
    return db.get(AppUser, user_id)


def find_alive_session(db: Session, token_hash: str, now: datetime) -> UserSession | None:
    """Phiên còn sống.

    Ba điều kiện nằm trong CÂU TRUY VẤN chứ không kiểm ở tầng service: quên một cái ở trên
    là một token đã thu hồi vẫn dùng được, và không có gì đỏ.

    `user` được nạp kèm (`lazy="joined"` trên quan hệ) vì đường nóng của MỌI request cần id
    của user ngay.
    """
    return db.scalars(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    ).first()
