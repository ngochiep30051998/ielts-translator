"""Phục vụ web app (SPA) từ chính FastAPI.

**Vì sao không để nền tảng lo việc này**, dù đó là cách hiển nhiên hơn — ba lý do độc lập,
mỗi lý do đủ để loại:

1. `tests/test_deploy_readiness.py::test_vercel_json_khong_duoc_co_rewrites` CẤM thêm
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


def thu_muc_static() -> Path | None:
    """Thư mục SPA đã build, hoặc `None` nếu chưa build.

    Vắng mặt là chuyện bình thường: chạy backend-only bằng `uv run ielts-api`, hoặc chạy
    pytest, thì không ai build web cả.
    """
    settings = get_settings()
    thu_muc = Path(settings.web_static_dir)
    if not thu_muc.is_absolute():
        thu_muc = API_SERVICE_ROOT / thu_muc
    return thu_muc if (thu_muc / "index.html").is_file() else None


def gan_web_app(app: FastAPI) -> None:
    """Lắp SPA vào app. Gọi SAU KHI đã include mọi router của API.

    Thứ tự có ý nghĩa tuyệt đối: catch-all khớp mọi đường dẫn, nên route nào khai sau nó sẽ
    không bao giờ nhận được request.
    """
    goc = thu_muc_static()
    if goc is None:
        # Ghi log rồi đi tiếp, KHÔNG ném. Ném ở đây biến một bộ test đang xanh thành
        # FileNotFoundError ở một file trông chẳng liên quan gì tới thứ vừa sửa.
        log.info("Không thấy SPA đã build — chạy ở chế độ chỉ-API.")
        return

    # Asset có hash trong tên nên cache được vĩnh viễn; `StaticFiles` đặt sẵn ETag/Last-Modified.
    if (goc / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=goc / "assets"), name="assets")

    index = goc / "index.html"

    # `api_route(methods=["GET", "HEAD"])` chứ KHÔNG `@app.get`.
    #
    # `Route` của Starlette tự thêm HEAD khi có GET, nhưng `APIRoute` của FastAPI thì KHÔNG.
    # Thiếu HEAD ở đây thì mọi đường dẫn của SPA trả 405 cho HEAD — và HEAD là thứ health
    # check, monitor lẫn trình thu thập liên kết dùng đầu tiên. `StaticFiles` ở trên không
    # dính vì nó là `Route` thật của Starlette; chỉ catch-all này dính.
    @app.api_route("/{duong_dan:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(duong_dan: str, request: Request) -> Response:
        """Trả `index.html` cho mọi đường dẫn không thuộc API — SPA tự định tuyến phía client.

        `/api/*` PHẢI rơi tiếp xuống handler 404 cũ và giữ nguyên hình dạng
        `{code, message, retryable}`. Nuốt nó ở đây là biến mọi lỗi gõ sai URL của API thành
        một trang HTML 200 — client sẽ cố parse JSON, thất bại, rồi báo "backend trả phản hồi
        không đọc được" thay vì "không tìm thấy endpoint".
        """
        if request.url.path.startswith(API_PREFIX):
            return _khong_tim_thay(request)

        # File thật có trong thư mục build (favicon, manifest, icon…) thì trả chính nó.
        # `resolve()` + kiểm cha là chốt chặn path traversal: `../../etc/passwd` phải không
        # ra khỏi được thư mục build.
        if duong_dan:
            ung_vien = (goc / duong_dan).resolve()
            if ung_vien.is_file() and goc.resolve() in ung_vien.parents:
                return FileResponse(ung_vien)

        # `no-cache` chứ không `no-store`: trình duyệt vẫn giữ bản sao nhưng luôn hỏi lại
        # trước khi dùng. Cache index.html là cách chắc chắn nhất để người dùng chạy mã cũ
        # trỏ vào asset đã bị xoá sau một lần deploy.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def _khong_tim_thay(request: Request) -> Response:
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
