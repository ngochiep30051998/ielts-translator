package com.hiepnn.ieltstranslator.quiz;

/** Ba loại quiz. Tên hằng đi thẳng vào cột {@code quiz_item.type} và vào JSON API. */
public enum QuizType {
    /** Gemini sinh câu chứa từ, che từ đích bằng "___". Chấm local. */
    FILL_BLANK,
    /** Gemini sinh 1 đáp án đúng + 3 mồi nhử. Chấm local bằng so index. */
    COLLOCATION_CHOICE,
    /** Đề bài là chính từ đó, không tốn call sinh đề. Gemini chấm. */
    FREE_WRITE
}
