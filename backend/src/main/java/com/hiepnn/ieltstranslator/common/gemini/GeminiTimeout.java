package com.hiepnn.ieltstranslator.common.gemini;

/**
 * Mức timeout cho mỗi loại việc gọi Gemini. Ba mức khác nhau vì độ dài output khác nhau
 * một bậc: dịch một từ trả vài trăm token, sinh một lô 10 câu quiz trả vài nghìn.
 * Dùng chung 15 giây thì hoặc là sinh quiz đứt giữa chừng, hoặc là một lượt dịch hỏng
 * bắt người dùng đợi 30 giây mới thấy lỗi.
 */
public enum GeminiTimeout {
    TRANSLATE,
    QUIZ_GENERATE,
    QUIZ_GRADE
}
