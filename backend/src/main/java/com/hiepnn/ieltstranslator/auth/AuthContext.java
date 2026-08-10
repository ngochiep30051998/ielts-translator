package com.hiepnn.ieltstranslator.auth;

import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.springframework.stereotype.Component;
import org.springframework.web.context.annotation.RequestScope;

/**
 * User của request hiện tại.
 *
 * <p>Bean {@code @RequestScope} chứ KHÔNG phải ThreadLocal tự quản: Tomcat tái dùng thread,
 * và một ThreadLocal quên dọn là request sau đọc nhầm user của request trước — tức là rò dữ
 * liệu giữa hai người, im lặng. Container tự dọn scope này.
 */
@Component
@RequestScope
public class AuthContext {

    private Long userId;

    /**
     * Id của người đang đăng nhập. Ném UNAUTHORIZED nếu chưa có.
     *
     * <p>Ném ở ĐÂY chứ không ở SessionFilter là cố ý: filter nằm ngoài phạm vi của
     * {@code @RestControllerAdvice}, nên lỗi ném từ đó không đi qua GlobalExceptionHandler
     * và sẽ mất hình dạng {code, message, retryable} mà toàn bộ UI đang dựa vào.
     */
    public Long requireUserId() {
        if (userId == null) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Cần đăng nhập để dùng chức năng này");
        }
        return userId;
    }

    /** null khi chưa đăng nhập. Chỉ dùng cho chỗ THẬT SỰ cho phép ẩn danh. */
    public Long userIdOrNull() {
        return userId;
    }

    void set(Long userId) {
        this.userId = userId;
    }
}
