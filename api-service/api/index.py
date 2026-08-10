"""Điểm vào của Vercel.

`vercel.json` rewrite MỌI đường dẫn về file này. Lý do: gói Hobby giới hạn 12 function mỗi
lần deploy, mà API có nhiều endpoint hơn thế — chia theo file là chạm trần ngay.

Migration KHÔNG chạy ở đây: xem ghi chú trong `app/startup.py`. Trên Vercel, schema do
Supabase quản lý (chạy `migrations/V*.sql` một lần bằng tay).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Awaitable, Callable, MutableMapping
from pathlib import Path
from typing import Any

# Vercel đặt working directory ở gốc project chứ không ở `api/`, nhưng không tự thêm gốc
# vào sys.path. Không có ba dòng này thì `import app.main` chết ngay lúc cold start với
# ModuleNotFoundError — mà log thì chỉ hiện ở dashboard, không hiện khi chạy local.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app as fastapi_app  # noqa: E402

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]

#: Đường dẫn của chính function này. Rewrite của Vercel THAY đường dẫn gốc bằng nó — không
#: chỉ định tuyến tới nó — nên nếu không khôi phục, FastAPI thấy mọi request đều là
#: `/api/index` và trả 404 cho toàn bộ API.
FUNCTION_PATH = "/api/index"

#: Header có thể mang đường dẫn gốc, thử theo thứ tự. Danh sách chứ không phải một cái:
#: Vercel không cam kết header nào, và đoán sai một cái là hỏng toàn bộ API.
CANDIDATE_HEADERS = (
    b"x-vercel-original-path",
    b"x-original-uri",
    b"x-forwarded-uri",
    b"x-rewrite-url",
    b"x-vercel-proxied-for-path",
)


def _headers(scope: Scope) -> dict[bytes, bytes]:
    return dict(scope.get("headers") or [])


def _duong_dan_goc(scope: Scope) -> str | None:
    """Đường dẫn người dùng thực sự gọi, lấy từ header do proxy để lại."""
    headers = _headers(scope)
    for ten in CANDIDATE_HEADERS:
        gia_tri = headers.get(ten)
        if gia_tri:
            duong_dan = gia_tri.decode("latin-1").split("?", 1)[0]
            if duong_dan.startswith("/") and duong_dan != FUNCTION_PATH:
                return duong_dan
    return None


async def _bao_khong_khoi_phuc_duoc(scope: Scope, send: Send) -> None:
    """Không đoán được đường dẫn gốc thì nói ra thứ mình ĐANG CÓ, thay vì trả 404 câm.

    404 câm ở đây là ca tệ nhất: mọi endpoint cùng hỏng, thông điệp giống hệt nhau, và
    không có gì phân biệt "sai cấu hình proxy" với "gõ sai URL".

    Chỉ liệt kê TÊN header, không kèm giá trị: `authorization` và `cookie` nằm trong cùng
    danh sách đó.
    """
    than = json.dumps(
        {
            "code": "INTERNAL",
            "message": (
                "Không khôi phục được đường dẫn gốc sau rewrite của Vercel. "
                "Header đang có: "
                + ", ".join(sorted(t.decode("latin-1") for t in _headers(scope)))
            ),
            "retryable": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 500,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(than)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": than})


class KhoiPhucDuongDan:
    """Trả lại đường dẫn gốc cho FastAPI sau khi Vercel đã viết đè nó.

    Đặt ở đây chứ không ở `app/main.py` vì đây là chuyện riêng của Vercel: chạy Docker hay
    `python -m app` thì đường dẫn không bao giờ bị viết đè, và một lớp middleware chỉ để
    sửa lỗi của một nền tảng không nên nằm trong đường chạy của mọi môi trường khác.
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or scope.get("path") != FUNCTION_PATH:
            await self._app(scope, receive, send)
            return

        goc = _duong_dan_goc(scope)
        if goc is None:
            await _bao_khong_khoi_phuc_duoc(scope, send)
            return

        scope = dict(scope)
        scope["path"] = goc
        scope["raw_path"] = goc.encode("utf-8")
        await self._app(scope, receive, send)


app = KhoiPhucDuongDan(fastapi_app)

__all__ = ["app"]
