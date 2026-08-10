package com.hiepnn.ieltstranslator.common;

public enum ErrorCode {
    GEMINI_QUOTA,
    GEMINI_UNAVAILABLE,
    PARSE_ERROR,
    TEXT_TOO_LONG,
    NOT_FOUND,
    /** Thiếu token, token rác/hết hạn/đã thu hồi, hoặc code OAuth không đổi được. */
    UNAUTHORIZED,
    /** Đăng nhập Google thành công nhưng email không nằm trong allowlist. Vĩnh viễn. */
    FORBIDDEN,
    /** Google token endpoint chết. Dùng GEMINI_UNAVAILABLE ở đây là nói dối trong log. */
    AUTH_UNAVAILABLE,
    INTERNAL
}
