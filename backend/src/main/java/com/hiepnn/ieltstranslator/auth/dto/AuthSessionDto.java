package com.hiepnn.ieltstranslator.auth.dto;

import java.time.Instant;

/**
 * @param token Bản GỐC của token phiên. Đây là lần duy nhất nó tồn tại ngoài thiết bị người
 *              dùng — DB chỉ giữ SHA-256 của nó.
 */
public record AuthSessionDto(String token, Instant expiresAt, AuthUserDto user) {
}
