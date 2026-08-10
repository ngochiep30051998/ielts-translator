package com.hiepnn.ieltstranslator.auth;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.List;

/**
 * @param googleClientSecret CHỈ sống ở backend. Không bao giờ được xuất hiện trong bundle
 *                           extension — client id thì công khai được, secret thì không.
 * @param allowedEmails      Danh sách email được phép đăng nhập. Rỗng = KHÓA HẾT, cố ý:
 *                           cấu hình thiếu phải làm hệ thống đóng lại chứ không mở toang.
 */
@ConfigurationProperties(prefix = "auth")
public record AuthProperties(String googleClientId,
                             String googleClientSecret,
                             String googleTokenUrl,
                             List<String> allowedEmails,
                             String extensionId,
                             int sessionDays,
                             int dailyGeminiCalls) {
}
