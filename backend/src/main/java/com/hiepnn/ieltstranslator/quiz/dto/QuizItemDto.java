package com.hiepnn.ieltstranslator.quiz.dto;

import com.hiepnn.ieltstranslator.quiz.QuizType;

import java.util.List;

/**
 * Đề bài gửi xuống panel. TUYỆT ĐỐI không chứa đáp án dưới bất kỳ dạng nào.
 *
 * <p>Người dùng nộp qua POST /api/quiz/answer và backend mới là nơi so đáp án.
 *
 * <p>Vì sao {@code term} là null với FILL_BLANK: đáp án của FILL_BLANK chính là dạng
 * đã bị che của {@code term} — đa số trường hợp là chuỗi giống hệt. Gửi kèm
 * {@code term} là gửi luôn đáp án, dù {@code payload.answer} không nằm trong DTO.
 *
 * <p>KHÔNG thêm {@code @JsonInclude(NON_NULL)}: mirror TypeScript khai
 * {@code string | null} chứ không phải optional, hai bên chỉ khớp khi khoá luôn có mặt.
 *
 * @param id           khoá chính quiz_item, dùng để nộp bài
 * @param type         quyết định field nào có mặt
 * @param vocabEntryId từ gốc trong sổ, panel dùng để tra lại
 * @param term         null với FILL_BLANK; non-null với COLLOCATION_CHOICE và FREE_WRITE
 * @param question     LUÔN non-null và khác rỗng với cả ba loại
 * @param sentence     câu chứa "___"; non-null CHỈ với FILL_BLANK
 * @param options      đúng 4 lựa chọn ĐÃ XÁO TRỘN SẴN lúc lưu item; non-null CHỈ với
 *                     COLLOCATION_CHOICE. Thứ tự này là thứ tự đã lưu trong DB —
 *                     không xáo lại lúc trả response, và panel KHÔNG được xáo lại,
 *                     vì câu trả lời là index trong chính mảng này.
 */
public record QuizItemDto(Long id,
                          QuizType type,
                          Long vocabEntryId,
                          String term,
                          String question,
                          String sentence,
                          List<String> options) {
}
