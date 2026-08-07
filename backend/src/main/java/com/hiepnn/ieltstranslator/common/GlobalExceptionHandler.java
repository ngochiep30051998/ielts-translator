package com.hiepnn.ieltstranslator.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
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

    /**
     * Bắt lỗi validate của @Valid @RequestBody (vd: text rỗng). Nếu không có handler này,
     * catch-all handleOther() bên dưới sẽ nuốt MethodArgumentNotValidException và trả nhầm
     * 500 INTERNAL thay vì 400 — xem task-1-report.md mục review.
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiError> handleValidation(MethodArgumentNotValidException ex) {
        // getFieldErrors() KHÔNG phủ hết: constraint cấp class (@AssertTrue đặt sai chỗ,
        // validator tự viết) sinh global error, và chỉ đọc field error sẽ cho ra
        // "Request không hợp lệ: " — một chuỗi cụt không nói được gì, mà không có gì đỏ.
        // Hôm nay getGlobalErrors() luôn rỗng nên nhánh này không đổi hành vi ca nào;
        // nó chỉ làm ca hỏng trong tương lai nói ra được lỗi của chính nó.
        String detail = java.util.stream.Stream.concat(
                        ex.getBindingResult().getFieldErrors().stream()
                                .map(e -> e.getField() + " " + e.getDefaultMessage()),
                        ex.getBindingResult().getGlobalErrors().stream()
                                .map(org.springframework.validation.ObjectError::getDefaultMessage))
                .collect(java.util.stream.Collectors.joining("; "));
        return ResponseEntity.badRequest()
                .body(new ApiError(ErrorCode.INTERNAL.name(),
                        "Request không hợp lệ: " + detail, false));
    }

    /**
     * Body không đọc được: JSON méo, hoặc giá trị enum sai (vd type="FILLBLANK").
     * Không có handler này thì handleOther() nuốt và trả 500 — sai, đây là lỗi của
     * request chứ không phải của server. @RestControllerAdvice chạy TRƯỚC
     * DefaultHandlerExceptionResolver nên nhánh 400 mặc định của Spring không bao giờ
     * có cơ hội chạy.
     *
     * <p>KHÔNG đưa ex.getMessage() vào response: nó chứa nguyên đoạn JSON người dùng gửi
     * và cả tên class nội bộ.
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiError> handleUnreadable(HttpMessageNotReadableException ex) {
        log.warn("Body không đọc được: {}", ex.getMostSpecificCause().getMessage());
        return ResponseEntity.badRequest()
                .body(new ApiError(ErrorCode.INTERNAL.name(),
                        "Request không đọc được: sai định dạng JSON hoặc sai giá trị enum",
                        false));
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
