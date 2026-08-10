package com.hiepnn.ieltstranslator.auth;

/** Danh tính lấy được từ Google. Chỉ những claim thực sự dùng tới. */
public record GoogleIdentity(String sub, String email, boolean emailVerified,
                             String name, String picture) {
}
