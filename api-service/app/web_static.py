"""Phục vụ web app (SPA) từ chính FastAPI.

**Vì sao không để nền tảng lo việc này**, dù đó là cách hiển nhiên hơn — ba lý do độc lập,
mỗi lý do đủ để loại:

1. `tests/test_deploy_readiness.py::test_vercel_json_must_not_have_rewrites` CẤM thêm
   `rewrites` vào `vercel.json`.
2. Về kỹ thuật, thêm `rewrites` khi preset FastAPI đang bật làm **toàn bộ API trả 404**:
   rewrite chạy TRƯỚC function và *thay* đường dẫn chứ không chỉ định tuyến. Đó chính là lỗi
   mà test ở trên được viết ra để canh.
3. Chế độ `services` của Vercel — cách đúng hiện nay cho nhiều service trong một project —
   bị khoá sau quyền tài khoản, không phải thứ dựa vào được.

Và một lý do nữa quan trọng hơn cả ba: **đường Docker phải khớp đường Vercel** (ràng buộc
#15). `Caddyfile` reverse_proxy TOÀN BỘ đường dẫn về `api-service:8080`, và docker-compose
không có service nào phục vụ file tĩnh. Nếu SPA chỉ tồn tại nhờ cấu hình riêng của Vercel
thì đường Docker vỡ, và vỡ theo kiểu chỉ phát hiện được khi tự dựng lại.

Để FastAPI tự phục vụ là cơ chế DUY NHẤT giống hệt nhau ở cả hai đường.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.common.errors import ErrorCode
from app.config import API_SERVICE_ROOT, get_settings

log = logging.getLogger(__name__)

#: Đường dẫn thuộc về API. Catch-all của SPA KHÔNG được chạm vào chúng.
API_PREFIX = "/api/"

#: File PHẢI luôn hỏi lại máy chủ trước khi dùng lại bản đã tải.
#:
#: `sw.js` là thứ trình duyệt tải về để biết CÓ BẢN MỚI HAY KHÔNG, và tên nó không mang
#: hash. Để trình duyệt tự quyết cache bao lâu thì lượt kiểm tra bản mới đem bản cũ so với
#: chính bản cũ — không bao giờ khác nhau, nên người dùng không bao giờ được báo.
NO_CACHE = frozenset({"sw.js"})


def static_dir() -> Path | None:
    """Thư mục SPA đã build, hoặc `None` nếu chưa build.

    Vắng mặt là chuyện bình thường: chạy backend-only bằng `uv run ielts-api`, hoặc chạy
    pytest, thì không ai build web cả.
    """
    settings = get_settings()
    static_path = Path(settings.web_static_dir)
    if not static_path.is_absolute():
        static_path = API_SERVICE_ROOT / static_path
    return static_path if (static_path / "index.html").is_file() else None


def mount_web_app(app: FastAPI) -> None:
    """Lắp SPA vào app. Gọi SAU KHI đã include mọi router của API.

    Thứ tự có ý nghĩa tuyệt đối: catch-all khớp mọi đường dẫn, nên route nào khai sau nó sẽ
    không bao giờ nhận được request.
    """
    static_root = static_dir()
    if static_root is None:
        # Ghi log rồi đi tiếp, KHÔNG ném. Ném ở đây biến một bộ test đang xanh thành
        # FileNotFoundError ở một file trông chẳng liên quan gì tới thứ vừa sửa.
        log.info("Không thấy SPA đã build — chạy ở chế độ chỉ-API.")
        return

    # Asset có hash trong tên nên cache được vĩnh viễn; `StaticFiles` đặt sẵn ETag/Last-Modified.
    if (static_root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_root / "assets"), name="assets")

    index = static_root / "index.html"

    # `api_route(methods=["GET", "HEAD"])` chứ KHÔNG `@app.get`.
    #
    # `Route` của Starlette tự thêm HEAD khi có GET, nhưng `APIRoute` của FastAPI thì KHÔNG.
    # Thiếu HEAD ở đây thì mọi đường dẫn của SPA trả 405 cho HEAD — và HEAD là thứ health
    # check, monitor lẫn trình thu thập liên kết dùng đầu tiên. `StaticFiles` ở trên không
    # dính vì nó là `Route` thật của Starlette; chỉ catch-all này dính.
    @app.api_route("/{spa_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(spa_path: str, request: Request) -> Response:
        """Trả `index.html` cho mọi đường dẫn không thuộc API — SPA tự định tuyến phía client.

        `/api/*` PHẢI rơi tiếp xuống handler 404 cũ và giữ nguyên hình dạng
        `{code, message, retryable}`. Nuốt nó ở đây là biến mọi lỗi gõ sai URL của API thành
        một trang HTML 200 — client sẽ cố parse JSON, thất bại, rồi báo "backend trả phản hồi
        không đọc được" thay vì "không tìm thấy endpoint".
        """
        if request.url.path.startswith(API_PREFIX):
            return _not_found(request)

        # File thật có trong thư mục build (favicon, manifest, icon…) thì trả chính nó.
        # `resolve()` + kiểm cha là chốt chặn path traversal: `../../etc/passwd` phải không
        # ra khỏi được thư mục build.
        if spa_path:
            candidate = (static_root / spa_path).resolve()
            if candidate.is_file() and static_root.resolve() in candidate.parents:
                if spa_path in NO_CACHE:
                    return FileResponse(candidate, headers={"Cache-Control": "no-cache"})
                return FileResponse(candidate)

        # `no-cache` chứ không `no-store`: trình duyệt vẫn giữ bản sao nhưng luôn hỏi lại
        # trước khi dùng. Cache index.html là cách chắc chắn nhất để người dùng chạy mã cũ
        # trỏ vào asset đã bị xoá sau một lần deploy.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def _not_found(request: Request) -> Response:
    """404 mang đúng hình dạng lỗi chung, y như handler ở `main.py`."""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=404,
        content={
            "code": ErrorCode.NOT_FOUND.value,
            "message": f"Not Found: {request.method} {request.url.path}",
            "retryable": False,
        },
    )
