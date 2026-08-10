"""Lỗi đi một đường duy nhất, hình dạng `{code, message, retryable}` (ràng buộc #4).

Bản port của `ErrorCode` + `AppException` + `GlobalExceptionHandler` bên Java.

Chỗ Python yếu hơn Java: `switch` exhaustive của Java làm việc thêm một `ErrorCode` mà
quên nhánh xử lý trở thành lỗi biên dịch. Python không có cơ chế đó. Phần bù gồm ba lớp:

* `assert_never()` ở cuối `status_for` — mypy báo lỗi khi thiếu nhánh;
* `test_error_code_mapping.py` duyệt qua từng giá trị enum và khẳng định có ánh xạ;
* `mypy --strict` trong quy trình kiểm tra.

Đừng thêm nhánh `else`/`case _` để né: nó làm cả ba lớp trên mù cùng lúc.
"""

from __future__ import annotations

import enum
import logging
from typing import assert_never

log = logging.getLogger(__name__)


class ErrorCode(enum.StrEnum):
    GEMINI_QUOTA = "GEMINI_QUOTA"
    GEMINI_UNAVAILABLE = "GEMINI_UNAVAILABLE"
    PARSE_ERROR = "PARSE_ERROR"
    TEXT_TOO_LONG = "TEXT_TOO_LONG"
    NOT_FOUND = "NOT_FOUND"
    #: Thiếu token, token rác/hết hạn/đã thu hồi, hoặc code OAuth không đổi được.
    UNAUTHORIZED = "UNAUTHORIZED"
    #: Đăng nhập Google thành công nhưng email không nằm trong allowlist. Vĩnh viễn.
    FORBIDDEN = "FORBIDDEN"
    #: Google token endpoint chết. Dùng GEMINI_UNAVAILABLE ở đây là nói dối trong log.
    AUTH_UNAVAILABLE = "AUTH_UNAVAILABLE"
    INTERNAL = "INTERNAL"


def status_for(code: ErrorCode) -> int:
    match code:
        case ErrorCode.NOT_FOUND:
            return 404
        case ErrorCode.TEXT_TOO_LONG:
            return 400
        case ErrorCode.GEMINI_QUOTA:
            return 429
        case ErrorCode.GEMINI_UNAVAILABLE | ErrorCode.AUTH_UNAVAILABLE:
            return 503
        case ErrorCode.UNAUTHORIZED:
            return 401
        case ErrorCode.FORBIDDEN:
            return 403
        case ErrorCode.PARSE_ERROR | ErrorCode.INTERNAL:
            return 500
    assert_never(code)


def _retryable(code: ErrorCode) -> bool:
    """Retry được = "cùng request đó, lát nữa có thể thành công".

    UNAUTHORIZED và FORBIDDEN cố ý KHÔNG thoả: một cái cần đăng nhập lại, cái kia cần được
    cấp quyền — cả hai là hành động khác, không phải bấm lại. Mời người dùng thử lại ở đó
    là chỉ sai đường hồi phục.
    """
    return code in (ErrorCode.GEMINI_UNAVAILABLE, ErrorCode.AUTH_UNAVAILABLE)


class AppError(Exception):
    """Bản port của `AppException`. Dựng qua `AppError.of(...)` để `retryable` được suy ra
    từ mã lỗi ở đúng một chỗ."""

    def __init__(self, code: ErrorCode, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    @staticmethod
    def of(code: ErrorCode, message: str) -> AppError:
        return AppError(code, message, _retryable(code))

    def body(self) -> dict[str, object]:
        return {"code": self.code.value, "message": self.message, "retryable": self.retryable}

    def status(self) -> int:
        return status_for(self.code)

    def __repr__(self) -> str:  # pragma: no cover - chỉ phục vụ log
        return f"AppError({self.code.value}, {self.message!r}, retryable={self.retryable})"
