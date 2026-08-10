package com.hiepnn.ieltstranslator.quiz.dto;

/**
 * Giải thích một câu ĐÃ trả lời. KHÔNG lưu xuống DB — sinh lúc người học bấm nút và chỉ
 * sống trong đúng một response.
 *
 * @param explanation   LUÔN non-null và khác rỗng, tiếng Việt. Bám theo câu trả lời của
 *                      người học khi họ có trả lời; chỉ giải thích đáp án khi họ bỏ qua.
 * @param answerMeaning LUÔN non-null và khác rỗng. Nghĩa tiếng Việt của từ/cụm đáp án
 *                      trong đúng ngữ cảnh câu.
 * @param sentenceEn    Câu tiếng Anh đi kèm bản dịch. CẶP ĐÔI với {@code sentenceVi}: cùng
 *                      null hoặc cùng non-null, không bao giờ một nửa. Cùng null xảy ra
 *                      đúng một ca — FREE_WRITE bị bỏ qua nên không có câu nào để dịch.
 * @param sentenceVi    Bản dịch tiếng Việt của {@code sentenceEn}.
 */
public record ExplanationDto(String explanation,
                             String answerMeaning,
                             String sentenceEn,
                             String sentenceVi) {
}
