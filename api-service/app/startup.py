"""Chạy migration rồi thoát — bước khởi động trước khi uvicorn lên.

Tách khỏi `main.py` có chủ ý. Chạy migration trong lifespan của FastAPI nghĩa là trên
Vercel, mỗi cold start của mỗi instance đều thử migrate — nhiều tiến trình cùng chạy
`ALTER TABLE` là công thức để khoá lẫn nhau. Ở đây migration là một bước tường minh:
container gọi nó một lần trước khi phục vụ request, còn Vercel thì không gọi (schema do
Supabase quản lý riêng).

    python -m app.startup
"""

from __future__ import annotations

import logging
import sys

from app.config import get_settings
from app.db import get_engine
from app.migrator import migrate

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s - %(message)s")
log = logging.getLogger("app.startup")


def main() -> int:
    settings = get_settings()
    try:
        applied = migrate(get_engine(), bootstrap_email=settings.auth_bootstrap_email)
    except ValueError as ex:
        # Cấu hình thiếu phải chặn app lại chứ không để nó chạy với dữ liệu sai.
        log.error("Không chạy được migration: %s", ex)
        return 1
    if applied:
        log.info("Đã áp dụng migration: %s", ", ".join(f"V{v}" for v in applied))
    else:
        log.info("Schema đã ở bản mới nhất, không có migration nào cần chạy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
