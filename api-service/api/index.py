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
from urllib.parse import unquote

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

#: Tham số mà `vercel.json` nhét đường dẫn gốc vào:
#: `"destination": "/api/index?__path=/$1"`.
#:
#: Dùng query string chứ KHÔNG dò header. Đọc header là đoán — Vercel không cam kết header
#: nào mang đường dẫn gốc, và thực tế thì không cái nào mang cả. Còn capture group trong
#: `destination` là thứ chính mình khai, nên nó có mặt hay không là chuyện kiểm chứng được
#: chứ không phải chuyện may rủi.
PATH_PARAM = "__path"

#: Header có thể mang đường dẫn gốc. Chỉ còn là đường lui: nếu một ngày Vercel đổi cách xử
#: lý query trong `destination`, những header này có thể cứu được — nhưng không được coi là
#: cơ chế chính.
CANDIDATE_HEADERS = (
    b"x-vercel-original-path",
    b"x-original-uri",
    b"x-forwarded-uri",
    b"x-rewrite-url",
)


def _headers(scope: Scope) -> dict[bytes, bytes]:
    return dict(scope.get("headers") or [])


def _split_query(scope: Scope) -> tuple[str | None, bytes]:
    """Tách `__path` khỏi query string, trả về (đường dẫn, query còn lại).

    Phải BỎ `__path` khỏi query trước khi giao cho FastAPI: để lại thì nó lọt vào mọi
    handler như một tham số lạ, và endpoint nào validate query chặt sẽ từ chối request hợp
    lệ.
    """
    raw = scope.get("query_string") or b""
    if not raw:
        return None, b""

    path: str | None = None
    remaining: list[str] = []
    for pair in raw.decode("latin-1").split("&"):
        if not pair:
            continue
        key, _, value = pair.partition("=")
        if key == PATH_PARAM:
            path = unquote(value)
        else:
            remaining.append(pair)
    return path, "&".join(remaining).encode("latin-1")


def _path_from_headers(scope: Scope) -> str | None:
    headers = _headers(scope)
    for name in CANDIDATE_HEADERS:
        value = headers.get(name)
        if value:
            path = value.decode("latin-1").split("?", 1)[0]
            if path.startswith("/") and path != FUNCTION_PATH:
                return path
    return None


async def _report_unrecoverable_path(scope: Scope, send: Send) -> None:
    """Không đoán được đường dẫn gốc thì nói ra thứ mình ĐANG CÓ, thay vì trả 404 câm.

    404 câm ở đây là ca tệ nhất: mọi endpoint cùng hỏng, thông điệp giống hệt nhau, và
    không có gì phân biệt "sai cấu hình proxy" với "gõ sai URL".

    Chỉ liệt kê TÊN header, không kèm giá trị: `authorization` và `cookie` nằm trong cùng
    danh sách đó.
    """
    body = json.dumps(
        {
            "code": "INTERNAL",
            "message": (
                "Không khôi phục được đường dẫn gốc sau rewrite của Vercel. "
                "Header đang có: "
                + ", ".join(sorted(name.decode("latin-1") for name in _headers(scope)))
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
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RestoreOriginalPath:
    """Trả lại đường dẫn gốc cho FastAPI sau khi Vercel đã viết đè nó.

    Đặt ở đây chứ không ở `app/main.py` vì đây là chuyện riêng của Vercel: chạy Docker hay
    `python -m app` thì đường dẫn không bao giờ bị viết đè, và một lớp middleware chỉ để
    sửa lỗi của một nền tảng không nên nằm trong đường chạy của mọi môi trường khác.

    Gắn qua `add_middleware` chứ KHÔNG bọc ngoài `app`. Runtime của Vercel tự dò xem biến
    `app` là ASGI hay WSGI; một instance của class lạ có thể bị dò nhầm, và lúc đó lớp này
    không bao giờ chạy — đúng triệu chứng đã gặp: mọi endpoint trả 404 `/api/index` mà
    không có dấu vết nào của middleware. Gắn vào bên trong thì `app` vẫn là một `FastAPI`
    nguyên vẹn, không còn gì để dò nhầm.
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or scope.get("path") != FUNCTION_PATH:
            await self._app(scope, receive, send)
            return

        from_query, remaining_query = _split_query(scope)
        original = from_query or _path_from_headers(scope)
        if original is None or not original.startswith("/") or original == FUNCTION_PATH:
            await _report_unrecoverable_path(scope, send)
            return

        scope = dict(scope)
        scope["path"] = original
        scope["raw_path"] = original.encode("utf-8")
        if from_query is not None:
            scope["query_string"] = remaining_query
        await self._app(scope, receive, send)


fastapi_app.add_middleware(RestoreOriginalPath)

#: Vercel tìm đúng biến tên `app`. Nó là `FastAPI` chứ không phải object bọc ngoài — xem
#: docstring của `RestoreOriginalPath`.
app = fastapi_app

__all__ = ["app"]
