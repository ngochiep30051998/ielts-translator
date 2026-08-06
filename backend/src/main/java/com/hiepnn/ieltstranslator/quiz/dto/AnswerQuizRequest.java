package com.hiepnn.ieltstranslator.quiz.dto;

import jakarta.validation.constraints.NotNull;

/**
 * @param quizItemId id của quiz_item đang làm
 * @param answer     LUÔN là string trên đường truyền, cho cả ba loại. Với
 *                   COLLOCATION_CHOICE đây là index 0-based dạng chuỗi ("0".."3");
 *                   backend tự parse. Chuỗi không parse được thành index hợp lệ tính
 *                   là TRẢ LỜI SAI, không phải lỗi request.
 *
 *                   <p>{@code @NotNull} chứ KHÔNG phải {@code @NotBlank}: chuỗi rỗng là
 *                   GIÁ TRỊ HỢP LỆ, nghĩa là "bỏ qua câu này". Người học không nghĩ ra
 *                   từ rồi bấm Nộp là thao tác học tập bình thường; @NotBlank biến nó
 *                   thành 400 lỗi đỏ VÀ không ghi dòng quiz_attempt nào, nên câu đó lại
 *                   hiện ở đề sau như chưa từng làm.
 *
 *                   <p>Độ dài KHÔNG chặn bằng @Size ở đây mà bằng kiểm tra thủ công trong
 *                   QuizService, để ném TEXT_TOO_LONG (400, đúng ngữ nghĩa) thay vì
 *                   INTERNAL — cùng cách TranslationService làm với MAX_TEXT_LENGTH.
 */
public record AnswerQuizRequest(
        @NotNull(message = "không được bỏ trống") Long quizItemId,
        @NotNull(message = "không được bỏ trống") String answer) {
}
