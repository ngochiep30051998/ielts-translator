"""Điểm lắp ráp ứng dụng FastAPI — bản thay `IeltsTranslatorApplication` + `CorsConfig` +
`GlobalExceptionHandler`.

Hợp đồng `/api/*` giữ nguyên tuyệt đối so với backend Spring: extension không được biết
backend đã đổi.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.router import router as auth_router
from app.common.errors import AppError, ErrorCode
from app.config import get_settings
from app.health.router import router as health_router
from app.quiz.router import router as quiz_router
from app.srs.router import router as srs_router
from app.translation.router import router as translation_router
from app.vocabulary.router import router as vocabulary_router

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="IELTS Translator API",
        # Tài liệu tự sinh tắt: đây là API riêng của một extension, không có người dùng
        # thứ hai cần đọc, và /docs là một bề mặt công khai nữa để phải nghĩ về.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # CORS chỉ mở cho đúng extension này (ràng buộc #7). ID rỗng = không mở cho ai —
    # cấu hình thiếu phải làm hệ thống đóng lại chứ không mở toang.
    if settings.extension_id.strip():
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.cors_origin],
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["*"],
        )

    _register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(translation_router)
    app.include_router(vocabulary_router)
    app.include_router(srs_router)
    app.include_router(quiz_router)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: Exception) -> Response:
        assert isinstance(exc, AppError)
        log.warning("AppError %s: %s", exc.code.value, exc.message)
        return JSONResponse(status_code=exc.status(), content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: Exception) -> Response:
        """Bắt lỗi validate của Pydantic (vd: text rỗng).

        Trả 400 chứ không 422 mặc định của FastAPI: hợp đồng cũ của Spring là 400, và
        extension phân nhánh theo status. Đổi sang 422 ở đây là làm hỏng phía client mà
        không có test nào bên backend đỏ.
        """
        assert isinstance(exc, RequestValidationError)
        chi_tiet = "; ".join(
            f"{'.'.join(str(p) for p in loi.get('loc', ())[1:])} {loi.get('msg', '')}".strip()
            for loi in exc.errors()
        )
        return JSONResponse(
            status_code=400,
            content={
                "code": ErrorCode.INTERNAL.value,
                "message": f"Request không hợp lệ: {chi_tiet}",
                "retryable": False,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: Exception) -> Response:
        """404 định tuyến, 405 sai method... vẫn phải mang hình dạng lỗi chuẩn.

        Không có handler này thì Starlette trả `{"detail": "Not Found"}` — một hình dạng
        thứ hai mà phía extension không biết đọc, và chỉ lộ ra khi gõ sai URL.
        """
        assert isinstance(exc, StarletteHTTPException)
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.INTERNAL
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code.value, "message": str(exc.detail), "retryable": False},
        )

    @app.middleware("http")
    async def handle_unexpected(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Catch-all tương đương `handleOther`.

        Phải là middleware chứ không phải `@app.exception_handler(Exception)`: handler cho
        `Exception` của Starlette ném lại lỗi sau khi trả response để server ghi log, và
        `TestClient` mặc định `raise_server_exceptions=True` sẽ dựng lại nó — tức là test
        thấy traceback thay vì thấy 500 có hình dạng chuẩn. Middleware chặn sớm hơn nên
        hành vi giống hệt production lẫn test.

        KHÔNG đưa nội dung lỗi vào response: nó chứa nguyên đoạn dữ liệu người dùng gửi và
        cả tên class nội bộ.
        """
        try:
            return await call_next(request)
        except AppError as exc:
            # Middleware chạy NGOÀI exception handler của router, nên AppError ném từ một
            # dependency (vd `current_user_id`) sẽ đi qua đây trước. Không lặp lại nhánh
            # này thì mọi lỗi 401 biến thành 500.
            log.warning("AppError %s: %s", exc.code.value, exc.message)
            return JSONResponse(status_code=exc.status(), content=exc.body())
        except Exception:
            log.exception("Unhandled exception")
            return JSONResponse(
                status_code=500,
                content={
                    "code": ErrorCode.INTERNAL.value,
                    "message": "Lỗi không xác định",
                    "retryable": False,
                },
            )


app: Any = create_app()
