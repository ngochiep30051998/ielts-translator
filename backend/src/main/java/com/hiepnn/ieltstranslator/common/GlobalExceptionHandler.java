package com.hiepnn.ieltstranslator.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(AppException.class)
    public ResponseEntity<ApiError> handleApp(AppException ex) {
        log.warn("AppException {}: {}", ex.code(), ex.getMessage());
        return ResponseEntity.status(statusFor(ex.code()))
                .body(new ApiError(ex.code().name(), ex.getMessage(), ex.retryable()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleOther(Exception ex) {
        log.error("Unhandled exception", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ApiError(ErrorCode.INTERNAL.name(), "Lỗi không xác định", false));
    }

    private HttpStatus statusFor(ErrorCode code) {
        return switch (code) {
            case NOT_FOUND -> HttpStatus.NOT_FOUND;
            case TEXT_TOO_LONG -> HttpStatus.BAD_REQUEST;
            case GEMINI_QUOTA -> HttpStatus.TOO_MANY_REQUESTS;
            case GEMINI_UNAVAILABLE -> HttpStatus.SERVICE_UNAVAILABLE;
            case PARSE_ERROR, INTERNAL -> HttpStatus.INTERNAL_SERVER_ERROR;
        };
    }
}
