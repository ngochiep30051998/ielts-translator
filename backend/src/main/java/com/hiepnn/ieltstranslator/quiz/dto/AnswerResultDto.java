package com.hiepnn.ieltstranslator.quiz.dto;

/**
 * Kết quả chấm một câu.
 *
 * @param correct         FILL_BLANK / COLLOCATION_CHOICE: so khớp đúng hay sai.
 *                        FREE_WRITE: {@code meaning_ok && grammar_ok} do Gemini trả.
 *                        {@code band_ok} CỐ Ý không tham gia — nhãn band là gợi ý
 *                        tham khảo, không phải sự thật.
 * @param score           FILL_BLANK / COLLOCATION_CHOICE: đúng 100 hoặc đúng 0.
 *                        FREE_WRITE: 0–100 do Gemini trả.
 * @param feedback        LUÔN non-null và khác rỗng, tiếng Việt. Với FILL_BLANK và
 *                        COLLOCATION_CHOICE khi trả lời SAI, chuỗi này CHỨA LUÔN đáp
 *                        án đúng — đó là cách duy nhất người học biết đáp án, vì
 *                        QuizItemDto không mang nó.
 * @param improvedVersion CHỈ FREE_WRITE mới có; lưu ở cột quiz_attempt.improved_version.
 *                        Với FILL_BLANK và COLLOCATION_CHOICE LUÔN null — không phải
 *                        "chưa có", mà là "loại này không có khái niệm câu viết lại".
 *                        Panel không được render khối đó khi null.
 */
public record AnswerResultDto(boolean correct,
                              int score,
                              String feedback,
                              String improvedVersion) {
}
