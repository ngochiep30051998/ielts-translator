package com.hiepnn.ieltstranslator.common;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ErrorCodeMappingTest {

    @Test
    @DisplayName("AUTH_UNAVAILABLE retry được; UNAUTHORIZED và FORBIDDEN thì không")
    void retryableFlagPerCode() {
        // retryable không phải chuyện thẩm mỹ: UI dùng nó để chọn giữa "thử lại sau ít
        // giây" và "đường này chết hẳn". Bảo người bị từ chối quyền hãy thử lại là chỉ sai
        // đường hồi phục.
        assertThat(AppException.of(ErrorCode.AUTH_UNAVAILABLE, "x").retryable()).isTrue();
        assertThat(AppException.of(ErrorCode.UNAUTHORIZED, "x").retryable()).isFalse();
        assertThat(AppException.of(ErrorCode.FORBIDDEN, "x").retryable()).isFalse();
        assertThat(AppException.of(ErrorCode.GEMINI_UNAVAILABLE, "x").retryable()).isTrue();
        assertThat(AppException.of(ErrorCode.NOT_FOUND, "x").retryable()).isFalse();
    }
}
