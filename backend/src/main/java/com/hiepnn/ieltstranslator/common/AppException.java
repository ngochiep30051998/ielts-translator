package com.hiepnn.ieltstranslator.common;

public class AppException extends RuntimeException {
    private final ErrorCode code;
    private final boolean retryable;

    public AppException(ErrorCode code, String message, boolean retryable) {
        super(message);
        this.code = code;
        this.retryable = retryable;
    }

    /**
     * Retry được = "cùng request đó, lát nữa có thể thành công".
     *
     * <p>UNAUTHORIZED và FORBIDDEN cố ý KHÔNG thoả: một cái cần đăng nhập lại, cái kia cần
     * được cấp quyền — cả hai là hành động khác, không phải bấm lại. Mời người dùng thử lại
     * ở đó là chỉ sai đường hồi phục.
     */
    public static AppException of(ErrorCode code, String message) {
        boolean retryable = code == ErrorCode.GEMINI_UNAVAILABLE
                || code == ErrorCode.AUTH_UNAVAILABLE;
        return new AppException(code, message, retryable);
    }

    public ErrorCode code() { return code; }
    public boolean retryable() { return retryable; }
}
