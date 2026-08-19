"""Chạy api-service từ dòng lệnh — chạy migration rồi lên server.

    python -m app                 # chạy thường
    python -m app --reload        # hot reload khi sửa file trong app/
    python -m app --port 9000     # đè cổng của .env cho một lần chạy

Địa chỉ và cổng mặc định lấy từ `SERVER_ADDRESS`/`SERVER_PORT` trong `.env` DÙNG CHUNG với
backend Spring, nên không phải gõ tay và không có chỗ nào để hai bên lệch nhau.

Trong container thì Dockerfile gọi `app.startup` rồi `uvicorn` riêng, vì ở đó cổng do
compose quyết định chứ không do `.env`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent


def _program_name() -> str:
    """Tên hiển thị ở dòng `usage:`.

    Có hai đường vào cùng một hàm — `uv run ielts-api` (console script) và `python -m app`.
    In sai tên là chỉ người đọc `--help` gõ một lệnh không tồn tại trên máy họ.
    """
    return "python -m app" if Path(sys.argv[0]).name == "__main__.py" else "ielts-api"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=_program_name(), description="Chạy api-service của IELTS Translator"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Tự khởi động lại khi sửa file trong app/ (chỉ dùng khi phát triển)",
    )
    parser.add_argument("--host", default=None, help="Mặc định: SERVER_ADDRESS trong .env")
    parser.add_argument("--port", type=int, default=None, help="Mặc định: SERVER_PORT trong .env")
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Bỏ qua bước chạy migration (dùng khi schema đã chắc chắn ở bản mới nhất)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    from app.config import get_settings
    from app.startup import main as run_migrations

    args = _parse_args(argv)

    # Migration chạy MỘT lần ở tiến trình cha, trước khi uvicorn dựng reloader. Tiến trình
    # con do reloader spawn ra import `app.main`, không import module này (guard
    # `__name__ == "__main__"` chặn), nên sửa file không kéo theo một lượt migrate nữa.
    if not args.skip_migrate:
        exit_code = run_migrations()
        if exit_code != 0:
            return exit_code

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=args.host or settings.server_address,
        port=args.port or settings.server_port,
        reload=args.reload,
        # Chỉ theo dõi `app/`. Không giới hạn thì watcher soi cả `.venv` (hàng chục nghìn
        # file) — tốn CPU và trên macOS thì chạm trần số file mở được.
        reload_dirs=[str(APP_DIR)] if args.reload else None,
        # `prompts/` không nằm trong `reload_dirs` nên sửa prompt KHÔNG tự nạp lại. Cố ý:
        # `PromptLoader` nhớ kết quả parse trong bộ nhớ tiến trình, và version prompt nằm
        # trong khoá cache — sửa prompt là việc phải khởi động lại tay để nhớ tăng `version:`.
        reload_includes=["*.py"] if args.reload else None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
