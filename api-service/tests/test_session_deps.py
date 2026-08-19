"""Bản port của `SessionFilterIT` — nhận diện phiên và bắt buộc đăng nhập.

Endpoint dùng làm mẫu là `/api/vocab`, y như bản Java: nó là endpoint cần token đơn giản
nhất, và dùng chính nó nghĩa là test này cũng canh luôn việc router vocabulary có gắn
`CurrentUserId` hay không.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import IT_TOKEN, UserFixture, sha256


def _open_session(
    db: Session, user_id: int, expires_at: datetime, revoked_at: datetime | None
) -> str:
    raw = f"sf-{expires_at.timestamp()}-{revoked_at}"
    db.execute(
        text(
            "INSERT INTO user_session (user_id, token_hash, last_used_at, expires_at, revoked_at) "
            "VALUES (:uid, :hash, now(), :exp, :rev)"
        ),
        {"uid": user_id, "hash": sha256(raw), "exp": expires_at, "rev": revoked_at},
    )
    db.commit()
    return raw


def test_missing_header_returns_401_with_correct_shape(client: Any, owner: UserFixture) -> None:
    """Hình dạng lỗi quan trọng ngang status: UI phân nhánh theo `code`, và một trang lỗi
    HTML từ tầng middleware sẽ làm nó hiện "lỗi không xác định"."""
    resp = client.get("/api/vocab")

    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "UNAUTHORIZED"
    assert body["message"]
    assert body["retryable"] is False


def test_garbage_token_returns_401(client: Any, owner: UserFixture) -> None:
    resp = client.get("/api/vocab", headers={"Authorization": "Bearer khong-phai-token"})
    assert resp.status_code == 401


def test_header_with_wrong_scheme_returns_401(client: Any, owner: UserFixture) -> None:
    """`Basic <token>` không được nhận nhầm thành Bearer."""
    resp = client.get("/api/vocab", headers={"Authorization": f"Basic {IT_TOKEN}"})
    assert resp.status_code == 401


def test_revoked_token_returns_401(client: Any, db: Session, owner: UserFixture) -> None:
    raw = _open_session(db, owner.id, datetime.now(UTC) + timedelta(days=30), datetime.now(UTC))
    resp = client.get("/api/vocab", headers={"Authorization": f"Bearer {raw}"})
    assert resp.status_code == 401


def test_expired_token_returns_401(client: Any, db: Session, owner: UserFixture) -> None:
    raw = _open_session(db, owner.id, datetime.now(UTC) - timedelta(days=1), None)
    resp = client.get("/api/vocab", headers={"Authorization": f"Bearer {raw}"})
    assert resp.status_code == 401


def test_health_requires_no_token(client: Any) -> None:
    """Bắt health đăng nhập là tự khoá mình ngoài cửa: đăng nhập hỏng thì không còn endpoint
    nào nói được backend còn sống hay không."""
    resp = client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "UP"
    assert body["dbConnected"] is True
    assert body["geminiConfigured"] is True


def test_valid_token_passes_through_to_handler(client: Any, owner: UserFixture) -> None:
    resp = client.get("/api/vocab", headers=owner.headers)
    assert resp.status_code == 200


def test_empty_bearer_returns_401(client: Any, owner: UserFixture) -> None:
    """`Authorization: Bearer ` (thiếu token) không được coi là đã đăng nhập."""
    resp = client.get("/api/vocab", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401
