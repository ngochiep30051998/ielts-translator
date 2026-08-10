"""GET /api/health — CÔNG KHAI, không cần token.

Kiểm tra hai thứ mà lỗi cấu hình hay xảy ra nhất và không tự lộ ra chỗ nào khác: nối được
database không, và GEMINI_API_KEY có được nạp vào tiến trình này không. `geminiConfigured`
là cách duy nhất phân biệt "quên đặt biến trong .env" với "đặt rồi nhưng khoá sai" —
trường hợp thứ hai chỉ lộ ra khi gọi thật.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1")).scalar()
        db_connected = True
    except Exception:
        # Nuốt lỗi có chủ ý: health endpoint phải trả lời được CẢ KHI database chết, nếu
        # không thì nó không phân biệt được "app chết" với "db chết".
        db.rollback()
        db_connected = False

    return {
        "status": "UP" if db_connected else "DOWN",
        "dbConnected": db_connected,
        "geminiConfigured": settings.gemini_configured,
    }
