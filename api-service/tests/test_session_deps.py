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

from tests.conftest import IT_TOKEN, NguoiDungTest, sha256


def _mo_phien(
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


def test_thieu_header_tra_401_dung_hinh_dang(client: Any, owner: NguoiDungTest) -> None:
    """Hình dạng lỗi quan trọng ngang status: UI phân nhánh theo `code`, và một trang lỗi
    HTML từ tầng middleware sẽ làm nó hiện "lỗi không xác định"."""
    resp = client.get("/api/vocab")

    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "UNAUTHORIZED"
    assert body["message"]
    assert body["retryable"] is False


def test_token_rac_tra_401(client: Any, owner: NguoiDungTest) -> None:
    resp = client.get("/api/vocab", headers={"Authorization": "Bearer khong-phai-token"})
    assert resp.status_code == 401


def test_header_sai_luoc_do_tra_401(client: Any, owner: NguoiDungTest) -> None:
    """`Basic <token>` không được nhận nhầm thành Bearer."""
    resp = client.get("/api/vocab", headers={"Authorization": f"Basic {IT_TOKEN}"})
    assert resp.status_code == 401


def test_token_da_thu_hoi_tra_401(client: Any, db: Session, owner: NguoiDungTest) -> None:
    raw = _mo_phien(db, owner.id, datetime.now(UTC) + timedelta(days=30), datetime.now(UTC))
    resp = client.get("/api/vocab", headers={"Authorization": f"Bearer {raw}"})
    assert resp.status_code == 401


def test_token_het_han_tra_401(client: Any, db: Session, owner: NguoiDungTest) -> None:
    raw = _mo_phien(db, owner.id, datetime.now(UTC) - timedelta(days=1), None)
    resp = client.get("/api/vocab", headers={"Authorization": f"Bearer {raw}"})
    assert resp.status_code == 401


def test_health_khong_can_token(client: Any) -> None:
    """Bắt health đăng nhập là tự khoá mình ngoài cửa: đăng nhập hỏng thì không còn endpoint
    nào nói được backend còn sống hay không."""
    resp = client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "UP"
    assert body["dbConnected"] is True
    assert body["geminiConfigured"] is True


def test_token_hop_le_di_lot_toi_handler(client: Any, owner: NguoiDungTest) -> None:
    resp = client.get("/api/vocab", headers=owner.headers)
    assert resp.status_code == 200


def test_bearer_rong_tra_401(client: Any, owner: NguoiDungTest) -> None:
    """`Authorization: Bearer ` (thiếu token) không được coi là đã đăng nhập."""
    resp = client.get("/api/vocab", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401
