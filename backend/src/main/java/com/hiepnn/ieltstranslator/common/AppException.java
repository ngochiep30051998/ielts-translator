package com.hiepnn.ieltstranslator.common;

public class AppException extends RuntimeException {
    private final ErrorCode code;
    private final boolean retryable;

    public AppException(ErrorCode code, String message, boolean retryable) {
        super(message);
        this.code = code;
        this.retryable = retryable;
    }

    public static AppException of(ErrorCode code, String message) {
        boolean retryable = code == ErrorCode.GEMINI_UNAVAILABLE;
        return new AppException(code, message, retryable);
    }

    public ErrorCode code() { return code; }
    public boolean retryable() { return retryable; }
}
