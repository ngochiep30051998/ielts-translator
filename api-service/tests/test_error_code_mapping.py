"""Bản port của `ErrorCodeMappingTest`, cộng phần bù cho việc Python không có switch
exhaustive như Java.

Bên Java, thêm một `ErrorCode` mà quên nhánh trong `statusFor()` là lỗi BIÊN DỊCH. Python
không có cơ chế đó, nên test này đảm nhiệm vai trò ấy: nó duyệt qua từng giá trị enum và
khẳng định có ánh xạ. Xoá test này là bỏ hàng rào duy nhất.
"""

from __future__ import annotations

import pytest

from app.common.errors import AppError, ErrorCode, status_for


def test_every_error_code_has_a_status_mapping() -> None:
    """Vai trò của `switch` exhaustive bên Java."""
    for code in ErrorCode:
        status = status_for(code)
        assert 400 <= status <= 599, f"{code} ánh xạ ra status vô nghĩa: {status}"


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (ErrorCode.NOT_FOUND, 404),
        (ErrorCode.TEXT_TOO_LONG, 400),
        (ErrorCode.GEMINI_QUOTA, 429),
        (ErrorCode.GEMINI_UNAVAILABLE, 503),
        (ErrorCode.AUTH_UNAVAILABLE, 503),
        (ErrorCode.UNAUTHORIZED, 401),
        (ErrorCode.FORBIDDEN, 403),
        (ErrorCode.PARSE_ERROR, 500),
        (ErrorCode.INTERNAL, 500),
    ],
)
def test_status_matches_the_java_version(code: ErrorCode, status: int) -> None:
    """Bảng này là hợp đồng với extension — nó phân nhánh theo status code."""
    assert status_for(code) == status


def test_retryable_flag_for_each_error_code() -> None:
    """AUTH_UNAVAILABLE retry được; UNAUTHORIZED và FORBIDDEN thì không.

    `retryable` không phải chuyện thẩm mỹ: UI dùng nó để chọn giữa "thử lại sau ít giây" và
    "đường này chết hẳn". Bảo người bị từ chối quyền hãy thử lại là chỉ sai đường hồi phục.
    """
    assert AppError.of(ErrorCode.AUTH_UNAVAILABLE, "x").retryable is True
    assert AppError.of(ErrorCode.UNAUTHORIZED, "x").retryable is False
    assert AppError.of(ErrorCode.FORBIDDEN, "x").retryable is False
    assert AppError.of(ErrorCode.GEMINI_UNAVAILABLE, "x").retryable is True
    assert AppError.of(ErrorCode.NOT_FOUND, "x").retryable is False


def test_error_body_shape() -> None:
    """Hợp đồng `{code, message, retryable}` (ràng buộc #4) — extension đọc đúng ba khoá này."""
    body = AppError.of(ErrorCode.TEXT_TOO_LONG, "Đoạn văn quá dài").body()
    assert body == {
        "code": "TEXT_TOO_LONG",
        "message": "Đoạn văn quá dài",
        "retryable": False,
    }


def test_error_code_names_match_the_old_contract() -> None:
    """Tên mã đi thẳng vào JSON. Đổi tên là làm hỏng extension mà không có gì đỏ ở đây."""
    assert {c.value for c in ErrorCode} == {
        "GEMINI_QUOTA",
        "GEMINI_UNAVAILABLE",
        "PARSE_ERROR",
        "TEXT_TOO_LONG",
        "NOT_FOUND",
        "UNAUTHORIZED",
        "FORBIDDEN",
        "AUTH_UNAVAILABLE",
        "INTERNAL",
    }
