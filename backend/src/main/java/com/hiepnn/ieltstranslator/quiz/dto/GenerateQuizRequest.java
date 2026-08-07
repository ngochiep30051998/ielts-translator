package com.hiepnn.ieltstranslator.quiz.dto;

import com.hiepnn.ieltstranslator.quiz.QuizType;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * Sinh đề cho ĐÚNG MỘT loại. Panel muốn nhiều loại thì gửi nhiều request TUẦN TỰ.
 *
 * <p>Vì sao một loại mỗi request: mỗi loại là một lượt gọi Gemini, mà một lượt gọi xấu
 * nhất mất 2 × 30s + 1s backoff = 61s (GeminiClient.MAX_ATTEMPTS = 2). Gộp ba loại vào
 * một request đẩy trường hợp xấu nhất lên ~122s, vượt mọi ngưỡng chờ hợp lý phía client,
 * và biến một loại hỏng thành mất trắng cả đề.
 *
 * <p>Đúng MỘT trong {@code vocabIds} / {@code count} được cung cấp. Ràng buộc diễn đạt
 * bằng @AssertTrue chứ không bằng AppException: request sai phải là HTTP 400.
 * GlobalExceptionHandler.handleValidation() bắt MethodArgumentNotValidException và trả
 * 400; còn AppException.of(ErrorCode.INTERNAL, …) lại rơi vào statusFor() và trả 500 —
 * sai ngữ nghĩa.
 *
 * @param vocabIds danh sách id từ chỉ định thẳng; bỏ qua điều kiện repetitions >= 1.
 *                 Thiếu field ≡ null (Jackson). Id không tồn tại thì bỏ qua, không lỗi.
 * @param count    số CÂU muốn sinh cho loại này. Mỗi từ sinh đúng 1 câu cho 1 loại,
 *                 nên đây cũng đúng bằng số từ được chọn.
 * @param type     bắt buộc, đúng một loại
 */
public record GenerateQuizRequest(
        @Size(min = 1, max = 50, message = "phải có từ 1 đến 50 phần tử")
        List<Long> vocabIds,

        @Min(value = 1, message = "phải >= 1")
        @Max(value = 50, message = "phải <= 50")
        Integer count,

        @NotNull(message = "bắt buộc")
        QuizType type) {

    /**
     * TÊN METHOD PHẢI BẮT ĐẦU BẰNG "is" VÀ TRẢ boolean.
     *
     * <p>Hibernate Validator chỉ đánh giá constraint đặt trên GETTER khi validate bean.
     * Đặt @AssertTrue lên method không theo quy ước getter (vd: exactlyOneSelector())
     * thì nó bị coi là method-level constraint và bị BỎ QUA IM LẶNG — request sai vẫn
     * đi lọt xuống service và nổ thành 500 thay vì 400.
     *
     * <p>Cũng KHÔNG được thay bằng constraint tự viết ở cấp class: cái đó sinh global
     * error, mà handleValidation() chỉ đọc getFieldErrors() — message sẽ rỗng.
     */
    @AssertTrue(message = "phải cung cấp đúng một trong vocabIds hoặc count")
    public boolean isExactlyOneSelector() {
        boolean hasIds = vocabIds != null && !vocabIds.isEmpty();
        boolean hasCount = count != null;
        return hasIds ^ hasCount;
    }
}
