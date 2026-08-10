package com.hiepnn.ieltstranslator.quiz.dto;

import jakarta.validation.constraints.NotNull;

/**
 * CỐ Ý chỉ mang {@code quizItemId} và không nhận câu trả lời từ client.
 *
 * <p>Response của endpoint này TIẾT LỘ ĐÁP ÁN, nên nó phải tự đọc {@code quiz_attempt} gần
 * nhất và từ chối khi chưa có lượt làm nào. Nhận câu trả lời do client gửi lên rồi tin luôn
 * là biến {@code /explain} thành đường vòng đọc đáp án trước khi trả lời — đúng thứ mà
 * QuizItemDto cố ý bảo vệ.
 */
public record ExplainQuizRequest(
        @NotNull(message = "không được bỏ trống") Long quizItemId) {
}
