package com.hiepnn.ieltstranslator.quiz;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
import com.hiepnn.ieltstranslator.quiz.dto.AnswerResultDto;
import com.hiepnn.ieltstranslator.quiz.dto.ExplanationDto;
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

    static final String EXPLAIN_FILL_BLANK_PROMPT = "quiz-explain-fill-blank.md";
    static final String EXPLAIN_COLLOCATION_PROMPT = "quiz-explain-collocation.md";
    static final String EXPLAIN_FREE_WRITE_PROMPT = "quiz-explain-free-write.md";

    /**
     * CHỈ hai field bắt buộc, và đó là chủ ý.
     *
     * <p>{@code sentence_en} không bắt buộc vì hai trong ba loại backend đã tự biết câu
     * tiếng Anh — nhờ Gemini chép lại một chuỗi đang cầm trong tay là mời nó chép sai.
     * {@code sentence_vi} không bắt buộc vì có đúng một ca không tồn tại câu nào để dịch
     * (FREE_WRITE bị bỏ qua); bắt buộc field đó là ép Gemini bịa ra một câu tiếng Việt
     * không gắn với câu tiếng Anh nào.
     */
    private static final Map<String, Object> EXPLAIN_SCHEMA = Map.of(
            "type", "object",
            "properties", Map.of(
                    "explanation_vi", Map.of("type", "string"),
                    "answer_meaning_vi", Map.of("type", "string"),
                    "sentence_en", Map.of("type", "string"),
                    "sentence_vi", Map.of("type", "string")),
            "required", List.of("explanation_vi", "answer_meaning_vi"));

    private final QuizGenerator generator;
    private final com.hiepnn.ieltstranslator.vocabulary.VocabService vocab;
    private final QuizCandidateRepository candidates;
    private final QuizItemRepository items;
    private final QuizAttemptRepository attempts;
    private final QuizGrader grader;
    private final GeminiClient gemini;
    private final PromptLoader prompts;
    private final com.hiepnn.ieltstranslator.quota.GeminiQuotaGuard quota;

    public QuizService(QuizGenerator generator,
                       com.hiepnn.ieltstranslator.vocabulary.VocabService vocab,
                       QuizCandidateRepository candidates,
                       QuizItemRepository items, QuizAttemptRepository attempts,
                       QuizGrader grader, GeminiClient gemini, PromptLoader prompts,
                       com.hiepnn.ieltstranslator.quota.GeminiQuotaGuard quota) {
        this.generator = generator;
        this.vocab = vocab;
        this.candidates = candidates;
        this.items = items;
        this.attempts = attempts;
        this.grader = grader;
        this.gemini = gemini;
        this.prompts = prompts;
        this.quota = quota;
    }

    /**
     * Trả MẢNG RỖNG khi không có ứng viên — đó là trạng thái "chưa ôn từ nào đủ điều
     * kiện", không phải lỗi. Ném ở đây sẽ buộc phải đẻ thêm một ErrorCode cho một tình
     * huống hoàn toàn bình thường.
     */
    @Transactional
    public List<QuizItemDto> generate(Long userId, GenerateQuizRequest request) {
        // request.vocabIds() đến THẲNG từ client. Không lọc thì người dùng đặt tay id của
        // người khác vào và nhận về đề chứa term + câu ví dụ trong sổ từ của họ.
        List<Long> vocabIds = (request.vocabIds() != null && !request.vocabIds().isEmpty())
                ? vocab.filterOwnedIds(userId, request.vocabIds())
                : candidates.findCandidates(userId, request.count());
        if (vocabIds.isEmpty()) {
            return List.of();
        }

        List<QuizItem> built = generator.buildItems(userId, vocabIds, request.type());
        List<QuizItemDto> out = new ArrayList<>(built.size());
        for (QuizItem item : built) {
            out.add(toDto(item));
        }
        return out;
    }

    @Transactional
    public AnswerResultDto answer(Long userId, Long quizItemId, String answer) {
        String given = answer == null ? "" : answer;
        if (given.length() > MAX_ANSWER_LENGTH) {
            throw AppException.of(ErrorCode.TEXT_TOO_LONG,
                    "Bài viết quá dài (tối đa " + MAX_ANSWER_LENGTH + " ký tự)");
        }

        QuizItem item = items.findOwned(quizItemId, userId)
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
            case FREE_WRITE -> gradeFreeWrite(userId, item, given);
        };
    }

    /**
     * Giải thích một câu ĐÃ trả lời. Không ghi gì xuống DB.
     *
     * <p>Chưa có lượt làm nào thì ném NOT_FOUND TRƯỚC khi gọi Gemini: response này chứa đáp
     * án nên nó không được phục vụ một request chưa trả lời, và cũng không được đốt quota
     * cho request đó.
     */
    @Transactional(readOnly = true)
    public ExplanationDto explain(Long userId, Long quizItemId) {
        // findOwned chứ không findById: /explain TIẾT LỘ ĐÁP ÁN, nên rò ở đây vừa là rò dữ
        // liệu vừa là đốt quota Gemini của người khác. Chốt chặn nằm TRƯỚC lượt gọi Gemini,
        // cùng chỗ với chốt "chưa trả lời thì 404".
        QuizItem item = items.findOwned(quizItemId, userId)
                .orElseThrow(() -> AppException.of(ErrorCode.NOT_FOUND,
                        "Không tìm thấy câu hỏi id=" + quizItemId));
        QuizAttempt attempt = attempts.findFirstByQuizItem_IdOrderByIdDesc(quizItemId)
                .orElseThrow(() -> AppException.of(ErrorCode.NOT_FOUND,
                        "Chưa trả lời câu này nên chưa có gì để giải thích"));

        // switch KHÔNG có nhánh default: thêm QuizType mới phải fail compile ở đây, đúng
        // nguyên tắc của toDto() và GlobalExceptionHandler.statusFor().
        ExplainInput input = switch (item.getType()) {
            case FILL_BLANK -> fillBlankInput(item, attempt);
            case COLLOCATION_CHOICE -> collocationInput(item, attempt);
            case FREE_WRITE -> freeWriteInput(item, attempt);
        };

        quota.consume(userId);
        PromptTemplate template = prompts.load(input.promptFile());
        JsonNode payload = gemini.generateJson(template.render(input.vars()),
                EXPLAIN_SCHEMA, GeminiTimeout.QUIZ_GRADE);

        String explanation = firstNonBlank(payload.path("explanation_vi").asText(""),
                "Chưa lấy được giải thích cho câu này.");
        String answerMeaning = firstNonBlank(payload.path("answer_meaning_vi").asText(""),
                meaningFromVocab(item), "(chưa có nghĩa)");

        // knownSentenceEn khác rỗng nghĩa là BACKEND biết câu tiếng Anh; lúc đó chuỗi Gemini
        // trả về bị bỏ qua hoàn toàn.
        String sentenceEn = input.knownSentenceEn().isBlank()
                ? payload.path("sentence_en").asText("")
                : input.knownSentenceEn();
        String sentenceVi = payload.path("sentence_vi").asText("");
        // Thiếu một nửa thì bỏ cả cặp. Trả một nửa là bắt panel render khối "Dịch câu" với
        // đúng một dòng trống.
        if (sentenceEn.isBlank() || sentenceVi.isBlank()) {
            sentenceEn = null;
            sentenceVi = null;
        }
        return new ExplanationDto(explanation, answerMeaning, sentenceEn, sentenceVi);
    }

    /**
     * Đầu vào đã chuẩn hoá cho một lượt giải thích.
     *
     * @param knownSentenceEn câu tiếng Anh backend đã biết. RỖNG nghĩa là backend không có
     *                        câu nào — hoặc vì loại đó cần Gemini nghĩ ra
     *                        (COLLOCATION_CHOICE), hoặc vì thật sự không có câu nào tồn tại
     *                        (FREE_WRITE bị bỏ qua). Cả hai ca đều xử lý giống nhau: lấy
     *                        {@code sentence_en} Gemini trả, rỗng thì bỏ cả cặp.
     */
    private record ExplainInput(String promptFile, Map<String, String> vars,
                                String knownSentenceEn) {
    }

    private ExplainInput fillBlankInput(QuizItem item, QuizAttempt attempt) {
        Map<String, Object> p = item.getPayload();
        VocabEntry v = item.getVocabEntry();
        String sentence = asString(p.get("sentence"));
        String answer = asString(p.get("answer"));
        // Câu đã điền đáp án ghép ở đây chứ không nhờ Gemini. Prompt sinh đề đã bảo đảm
        // "___" xuất hiện đúng một lần trong câu.
        String filled = sentence.replace("___", answer);
        return new ExplainInput(EXPLAIN_FILL_BLANK_PROMPT, Map.of(
                "SENTENCE", sentence,
                "ANSWER", answer,
                "TERM", nullToEmpty(v.getTerm()),
                "POS", nullToEmpty(v.getPos()),
                "MEANING_VI", nullToEmpty(v.getMeaningVi()),
                "USER_ANSWER", nullToEmpty(attempt.getUserAnswer())),
                filled);
    }

    private ExplainInput collocationInput(QuizItem item, QuizAttempt attempt) {
        Map<String, Object> p = item.getPayload();
        VocabEntry v = item.getVocabEntry();
        List<String> options = asStringList(p.get("options"));
        int correctIndex = asInt(p.get("correct_index"));
        String correctOption = (correctIndex >= 0 && correctIndex < options.size())
                ? options.get(correctIndex) : "";

        StringBuilder rendered = new StringBuilder();
        for (int i = 0; i < options.size(); i++) {
            rendered.append(i + 1).append(". ").append(options.get(i)).append('\n');
        }

        return new ExplainInput(EXPLAIN_COLLOCATION_PROMPT, Map.of(
                "TERM", nullToEmpty(v.getTerm()),
                "POS", nullToEmpty(v.getPos()),
                "MEANING_VI", nullToEmpty(v.getMeaningVi()),
                "QUESTION", asString(p.get("question")),
                "OPTIONS", rendered.toString().strip(),
                "ANSWER", correctOption,
                // Câu trả lời lưu trong attempt là INDEX dạng chuỗi. Dịch ngược ra nội
                // dung cụm ngay tại đây: đưa "2" vào prompt thì Gemini không biết người
                // học đã chọn gì.
                "USER_ANSWER", optionAt(options, nullToEmpty(attempt.getUserAnswer()))),
                "");
    }

    /** Chuỗi không parse được thành index hợp lệ — kể cả rỗng, tức bỏ qua — trả chuỗi rỗng. */
    private String optionAt(List<String> options, String rawIndex) {
        try {
            int index = Integer.parseInt(rawIndex.strip());
            return (index >= 0 && index < options.size()) ? options.get(index) : "";
        } catch (NumberFormatException e) {
            return "";
        }
    }

    private ExplainInput freeWriteInput(QuizItem item, QuizAttempt attempt) {
        VocabEntry v = item.getVocabEntry();
        String userAnswer = nullToEmpty(attempt.getUserAnswer());
        // Câu viết lại là câu mẫu đáng học nhất; không có thì lấy chính câu người học.
        // Bỏ qua câu thì cả hai đều rỗng — lúc đó KHÔNG có câu nào để dịch, và cặp
        // sentenceEn/sentenceVi sẽ cùng về null ở chỗ ghép kết quả.
        String sentenceEn = firstNonBlank(nullToEmpty(attempt.getImprovedVersion()), userAnswer);
        return new ExplainInput(EXPLAIN_FREE_WRITE_PROMPT, Map.of(
                "TERM", nullToEmpty(v.getTerm()),
                "POS", nullToEmpty(v.getPos()),
                "MEANING_VI", nullToEmpty(v.getMeaningVi()),
                "DEFINITION_EN", nullToEmpty(v.getDefinitionEn()),
                "USER_ANSWER", userAnswer,
                "SENTENCE_EN", sentenceEn),
                sentenceEn);
    }

    /** Nghĩa lấy từ chính sổ từ của người dùng, làm lưới hứng khi Gemini trả rỗng. */
    private String meaningFromVocab(QuizItem item) {
        VocabEntry v = item.getVocabEntry();
        return (v.getMeaningVi() == null || v.getMeaningVi().isBlank())
                ? "" : v.getTerm() + " = " + v.getMeaningVi();
    }

    /** Giá trị đầu tiên khác rỗng; hết sạch thì trả chuỗi rỗng. */
    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return "";
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

    private AnswerResultDto gradeFreeWrite(Long userId, QuizItem item, String given) {
        quota.consume(userId);
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
