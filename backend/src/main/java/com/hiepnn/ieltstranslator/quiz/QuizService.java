package com.hiepnn.ieltstranslator.quiz;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
import com.hiepnn.ieltstranslator.quiz.dto.AnswerResultDto;
import com.hiepnn.ieltstranslator.quiz.dto.GenerateQuizRequest;
import com.hiepnn.ieltstranslator.quiz.dto.QuizItemDto;
import com.hiepnn.ieltstranslator.translation.PromptLoader;
import com.hiepnn.ieltstranslator.translation.PromptTemplate;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class QuizService {

    /** Giới hạn cứng phía server; QuizTab phía extension cũng chặn ở CÙNG con số. */
    private static final int MAX_ANSWER_LENGTH = 1000;

    private static final Map<String, Object> GRADE_SCHEMA = Map.of(
            "type", "object",
            "properties", Map.of(
                    "meaning_ok", Map.of("type", "boolean"),
                    "grammar_ok", Map.of("type", "boolean"),
                    "band_ok", Map.of("type", "boolean"),
                    "score", Map.of("type", "integer"),
                    "feedback_vi", Map.of("type", "string"),
                    "improved_version", Map.of("type", "string")),
            "required", List.of("meaning_ok", "grammar_ok", "band_ok", "score", "feedback_vi"));

    private final QuizGenerator generator;
    private final QuizCandidateRepository candidates;
    private final QuizItemRepository items;
    private final QuizAttemptRepository attempts;
    private final QuizGrader grader;
    private final GeminiClient gemini;
    private final PromptLoader prompts;

    public QuizService(QuizGenerator generator, QuizCandidateRepository candidates,
                       QuizItemRepository items, QuizAttemptRepository attempts,
                       QuizGrader grader, GeminiClient gemini, PromptLoader prompts) {
        this.generator = generator;
        this.candidates = candidates;
        this.items = items;
        this.attempts = attempts;
        this.grader = grader;
        this.gemini = gemini;
        this.prompts = prompts;
    }

    /**
     * Trả MẢNG RỖNG khi không có ứng viên — đó là trạng thái "chưa ôn từ nào đủ điều
     * kiện", không phải lỗi. Ném ở đây sẽ buộc phải đẻ thêm một ErrorCode cho một tình
     * huống hoàn toàn bình thường.
     */
    @Transactional
    public List<QuizItemDto> generate(GenerateQuizRequest request) {
        List<Long> vocabIds = (request.vocabIds() != null && !request.vocabIds().isEmpty())
                ? request.vocabIds()
                : candidates.findCandidates(request.count());
        if (vocabIds.isEmpty()) {
            return List.of();
        }

        List<QuizItem> built = generator.buildItems(vocabIds, request.type());
        List<QuizItemDto> out = new ArrayList<>(built.size());
        for (QuizItem item : built) {
            out.add(toDto(item));
        }
        return out;
    }

    @Transactional
    public AnswerResultDto answer(Long quizItemId, String answer) {
        String given = answer == null ? "" : answer;
        if (given.length() > MAX_ANSWER_LENGTH) {
            throw AppException.of(ErrorCode.TEXT_TOO_LONG,
                    "Bài viết quá dài (tối đa " + MAX_ANSWER_LENGTH + " ký tự)");
        }

        QuizItem item = items.findById(quizItemId)
                .orElseThrow(() -> AppException.of(ErrorCode.NOT_FOUND,
                        "Không tìm thấy câu hỏi id=" + quizItemId));

        if (given.isBlank()) {
            // Bỏ qua câu: chấm 0 và ghi lịch sử như một lượt làm THẬT. Không ghi thì item
            // vẫn lọt findReusable và câu đã bỏ qua sẽ hiện lại ở đề sau như chưa từng làm.
            // KHÔNG gọi Gemini — chấm một bài viết rỗng là đốt quota để nhận về một lời
            // chê hiển nhiên.
            return record(item, given, false, 0, "Chưa trả lời.", null);
        }

        return switch (item.getType()) {
            case FILL_BLANK -> gradeFillBlank(item, given);
            case COLLOCATION_CHOICE -> gradeCollocation(item, given);
            case FREE_WRITE -> gradeFreeWrite(item, given);
        };
    }

    /**
     * Ghi một lượt làm bài rồi trả kết quả. Thêm dòng mới mỗi lượt, KHÔNG ghi đè:
     * quiz_attempt là lịch sử, và số lượt làm chính là tiêu chí xếp ưu tiên ứng viên cho
     * lần sinh đề sau. Mọi đường chấm đều phải đi qua đây — bỏ sót một đường là câu đó
     * không bao giờ được coi là đã làm.
     */
    private AnswerResultDto record(QuizItem item, String given, boolean correct, int score,
                                   String feedback, String improvedVersion) {
        QuizAttempt attempt = new QuizAttempt();
        attempt.setQuizItem(item);
        attempt.setUserAnswer(given);
        attempt.setCorrect(correct);
        attempt.setScore(score);
        attempt.setAiFeedback(feedback);
        attempt.setImprovedVersion(improvedVersion);
        attempts.save(attempt);
        return new AnswerResultDto(correct, score, feedback, improvedVersion);
    }

    private AnswerResultDto gradeFillBlank(QuizItem item, String given) {
        String expected = asString(item.getPayload().get("answer"));
        boolean correct = grader.gradeFillBlank(given, expected);
        // Khi sai, feedback CHỨA LUÔN đáp án đúng — QuizItemDto cố ý không mang nó, nên
        // đây là kênh duy nhất người học biết đáp án.
        return record(item, given, correct, correct ? 100 : 0,
                correct ? "Chính xác." : "Chưa đúng. Đáp án: " + expected, null);
    }

    private AnswerResultDto gradeCollocation(QuizItem item, String given) {
        List<String> options = asStringList(item.getPayload().get("options"));
        int correctIndex = asInt(item.getPayload().get("correct_index"));
        boolean correct = grader.gradeCollocation(given, correctIndex);
        String correctOption = (correctIndex >= 0 && correctIndex < options.size())
                ? options.get(correctIndex) : "";
        return record(item, given, correct, correct ? 100 : 0,
                correct ? "Chính xác." : "Chưa đúng. Đáp án: " + correctOption, null);
    }

    private AnswerResultDto gradeFreeWrite(QuizItem item, String given) {
        VocabEntry entry = item.getVocabEntry();
        PromptTemplate template = prompts.load(QuizGenerator.GRADE_PROMPT);
        String prompt = template.render(Map.of(
                "TERM", nullToEmpty(entry.getTerm()),
                "POS", nullToEmpty(entry.getPos()),
                "MEANING_VI", nullToEmpty(entry.getMeaningVi()),
                "DEFINITION_EN", nullToEmpty(entry.getDefinitionEn()),
                "ANSWER", given));

        JsonNode payload = gemini.generateJson(prompt, GRADE_SCHEMA, GeminiTimeout.QUIZ_GRADE);

        // band_ok CỐ Ý không tham gia vào correct: nhãn band là gợi ý tham khảo, không
        // phải sự thật — trượt band mà dùng từ đúng nghĩa, đúng ngữ pháp thì vẫn là đúng.
        boolean correct = payload.path("meaning_ok").asBoolean(false)
                && payload.path("grammar_ok").asBoolean(false);
        int score = Math.clamp(payload.path("score").asInt(0), 0, 100);
        String feedback = payload.path("feedback_vi").asText("");
        if (feedback.isBlank()) {
            feedback = correct ? "Câu dùng từ hợp lý." : "Câu chưa đạt, xem lại cách dùng từ.";
        }
        String improved = payload.path("improved_version").asText(null);
        return record(item, given, correct, score, feedback,
                (improved == null || improved.isBlank()) ? null : improved);
    }

    /**
     * Điểm nghẽn duy nhất giữa payload (CÓ đáp án) và HTTP (KHÔNG có đáp án). Mọi field
     * đều lấy tường minh từ payload; KHÔNG bao giờ đổ nguyên payload vào DTO.
     *
     * <p>{@code switch} trên enum không có nhánh {@code default} — thêm QuizType mới sau
     * này phải fail compile ở đây, đúng nguyên tắc của GlobalExceptionHandler.statusFor().
     */
    private QuizItemDto toDto(QuizItem item) {
        Map<String, Object> p = item.getPayload();
        VocabEntry v = item.getVocabEntry();
        return switch (item.getType()) {
            // term = null: với FILL_BLANK, term CHÍNH LÀ đáp án. Gửi kèm là lộ đáp án dù
            // payload.answer không nằm trong DTO.
            case FILL_BLANK -> new QuizItemDto(item.getId(), item.getType(), v.getId(), null,
                    "Điền từ còn thiếu vào chỗ trống. Gợi ý: " + asString(p.get("hint")),
                    asString(p.get("sentence")), null);
            // options giữ NGUYÊN thứ tự đã lưu — đã xáo một lần lúc sinh item rồi.
            case COLLOCATION_CHOICE -> new QuizItemDto(item.getId(), item.getType(), v.getId(),
                    v.getTerm(), asString(p.get("question")), null,
                    asStringList(p.get("options")));
            case FREE_WRITE -> new QuizItemDto(item.getId(), item.getType(), v.getId(),
                    v.getTerm(), asString(p.get("question")), null, null);
        };
    }

    private String asString(Object value) {
        return value == null ? "" : value.toString();
    }

    @SuppressWarnings("unchecked")
    private List<String> asStringList(Object value) {
        if (!(value instanceof List<?> list)) {
            return List.of();
        }
        return (List<String>) list;
    }

    private int asInt(Object value) {
        return value instanceof Number number ? number.intValue() : -1;
    }

    private String nullToEmpty(String value) {
        return value == null ? "" : value;
    }
}
