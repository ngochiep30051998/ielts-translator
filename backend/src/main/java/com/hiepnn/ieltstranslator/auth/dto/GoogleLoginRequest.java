package com.hiepnn.ieltstranslator.auth.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * @param redirectUri Gửi lên để backend SO SÁNH, không phải để backend dùng theo. Giá trị
 *                    thật luôn được dựng lại từ EXTENSION_ID phía server.
 */
public record GoogleLoginRequest(
        @NotBlank(message = "không được bỏ trống") String code,
        @NotBlank(message = "không được bỏ trống") String redirectUri) {
}
