package com.hiepnn.ieltstranslator.quiz;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
import com.hiepnn.ieltstranslator.translation.PromptLoader;
import com.hiepnn.ieltstranslator.translation.PromptTemplate;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;

/**
 * Sinh đề quiz theo LÔ: một lượt gọi Gemini cho cả nhóm từ cùng loại, không phải mỗi từ
 * một lượt. 10 từ FILL_BLANK = 1 call.
 *
 * <p>Thứ tự ưu tiên là TÁI DÙNG TRƯỚC, SINH SAU: item cũ còn đúng prompt_version và chưa
 * ai làm thì dùng lại, nên mở lại màn quiz không tốn call nào.
 */
@Component
public class QuizGenerator {

    private static final Logger log = LoggerFactory.getLogger(QuizGenerator.class);

    static final String FILL_BLANK_PROMPT = "quiz-fill-blank.md";
    static final String COLLOCATION_PROMPT = "quiz-collocation.md";
    static final String GRADE_PROMPT = "quiz-grade-free-write.md";

    /** Schema structured output cho lô câu điền từ. */
    private static final Map<String, Object> FILL_BLANK_SCHEMA = Map.of(
            "type", "object",
            "properties", Map.of("items", Map.of(
                    "type", "array",
                    "items", Map.of(
                            "type", "object",
                            "properties", Map.of(
                                    "term", Map.of("type", "string"),
                                    "sentence", Map.of("type", "string"),
                                    "answer", Map.of("type", "string"),
                                    "hint", Map.of("type", "string")),
                            "required", List.of("term", "sentence", "answer", "hint")))),
            "required", List.of("items"));

    /** Schema structured output cho lô câu chọn collocation. */
    private static final Map<String, Object> COLLOCATION_SCHEMA = Map.of(
            "type", "object",
            "properties", Map.of("items", Map.of(
                    "type", "array",
                    "items", Map.of(
                            "type", "object",
                            "properties", Map.of(
                                    "term", Map.of("type", "string"),
                                    "question", Map.of("type", "string"),
                                    "options", Map.of("type", "array",
                                                      "items", Map.of("type", "string")),
                                    "correct_index", Map.of("type", "integer")),
                            "required", List.of("term", "question", "options", "correct_index")))),
            "required", List.of("items"));

    private final VocabEntryRepository vocab;
    private final QuizItemRepository items;
    private final QuizItemValidator validator;
    private final GeminiClient gemini;
    private final PromptLoader prompts;
    private final Random random = new Random();

    public QuizGenerator(VocabEntryRepository vocab, QuizItemRepository items,
                         QuizItemValidator validator, GeminiClient gemini, PromptLoader prompts) {
        this.vocab = vocab;
        this.items = items;
        this.validator = validator;
        this.gemini = gemini;
        this.prompts = prompts;
    }

    /** Version prompt quyết định item loại này còn hiệu lực hay không. */
    public int promptVersionFor(QuizType type) {
        return switch (type) {
            case FILL_BLANK -> prompts.load(FILL_BLANK_PROMPT).version();
            case COLLOCATION_CHOICE -> prompts.load(COLLOCATION_PROMPT).version();
            // FREE_WRITE không có prompt sinh đề; prompt chấm là thứ duy nhất ảnh hưởng
            // tới loại này, nên tăng version prompt chấm làm đề FREE_WRITE cũ hết hiệu lực.
            case FREE_WRITE -> prompts.load(GRADE_PROMPT).version();
        };
    }

    /**
     * Dựng đề cho ĐÚNG MỘT loại. Một loại mỗi lượt là hình dạng của endpoint
     * {@code POST /api/quiz/generate} — gộp nhiều loại đẩy trường hợp xấu nhất lên gấp
     * đôi và biến một loại hỏng thành mất trắng cả đề.
     *
     * @return item theo đúng thứ tự {@code vocabIds}; từ nào Gemini trả về hỏng thì vắng
     *         mặt. Rỗng khi không có từ nào hợp lệ để hỏi.
     * @throws AppException mã {@code PARSE_ERROR} khi có từ để hỏi mà không dựng nổi item
     *         nào — trả mảng rỗng lúc đó là giả vờ thành công.
     */
    public List<QuizItem> buildItems(List<Long> vocabIds, QuizType type) {
        List<VocabEntry> entries = loadInRequestedOrder(vocabIds);
        if (entries.isEmpty()) {
            return List.of();
        }

        int promptVersion = promptVersionFor(type);
        Map<Long, QuizItem> byEntry = reusableByEntry(entries, type, promptVersion);

        List<VocabEntry> needGeneration = entries.stream()
                .filter(entry -> !byEntry.containsKey(entry.getId()))
                .toList();
        if (!needGeneration.isEmpty()) {
            byEntry.putAll(generate(needGeneration, type, promptVersion));
        }

        List<QuizItem> result = new ArrayList<>(entries.size());
        for (VocabEntry entry : entries) {
            QuizItem item = byEntry.get(entry.getId());
            if (item != null) {
                result.add(item);
            }
        }
        if (result.isEmpty()) {
            throw AppException.of(ErrorCode.PARSE_ERROR,
                    "Gemini không trả được câu hỏi nào hợp lệ, thử tạo đề lại");
        }
        return result;
    }

    /** Bỏ qua id không tồn tại (hợp đồng: id lạ không phải lỗi) và giữ thứ tự người gọi. */
    private List<VocabEntry> loadInRequestedOrder(List<Long> vocabIds) {
        if (vocabIds == null || vocabIds.isEmpty()) {
            return List.of();
        }
        Map<Long, VocabEntry> found = new HashMap<>();
        vocab.findAllById(vocabIds).forEach(entry -> found.put(entry.getId(), entry));
        List<VocabEntry> ordered = new ArrayList<>(vocabIds.size());
        for (Long id : vocabIds) {
            VocabEntry entry = found.get(id);
            if (entry != null && !ordered.contains(entry)) {
                ordered.add(entry);
            }
        }
        return ordered;
    }

    /** Mỗi từ lấy tối đa MỘT item tái dùng. */
    private Map<Long, QuizItem> reusableByEntry(List<VocabEntry> entries, QuizType type,
                                                int promptVersion) {
        List<Long> ids = entries.stream().map(VocabEntry::getId).toList();
        Map<Long, QuizItem> byEntry = new LinkedHashMap<>();
        for (QuizItem item : items.findReusable(ids, List.of(type), promptVersion)) {
            byEntry.putIfAbsent(item.getVocabEntry().getId(), item);
        }
        return byEntry;
    }

    private Map<Long, QuizItem> generate(List<VocabEntry> entries, QuizType type,
                                         int promptVersion) {
        return switch (type) {
            case FREE_WRITE -> buildFreeWrite(entries, promptVersion);
            case FILL_BLANK -> callGemini(entries, type, promptVersion,
                    FILL_BLANK_PROMPT, FILL_BLANK_SCHEMA);
            case COLLOCATION_CHOICE -> callGemini(entries, type, promptVersion,
                    COLLOCATION_PROMPT, COLLOCATION_SCHEMA);
        };
    }

    /** FREE_WRITE dựng thẳng từ sổ từ — không tốn call Gemini nào lúc sinh đề. */
    private Map<Long, QuizItem> buildFreeWrite(List<VocabEntry> entries, int promptVersion) {
        Map<Long, QuizItem> built = new LinkedHashMap<>();
        for (VocabEntry entry : entries) {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("question", "Viết một câu tiếng Anh dùng từ \"" + entry.getTerm()
                    + "\" (" + nullToEmpty(entry.getMeaningVi()) + ").");
            built.put(entry.getId(),
                    save(entry, QuizType.FREE_WRITE, payload, promptVersion));
        }
        return built;
    }

    private Map<Long, QuizItem> callGemini(List<VocabEntry> entries, QuizType type,
                                           int promptVersion, String promptFile,
                                           Map<String, Object> schema) {
        PromptTemplate template = prompts.load(promptFile);
        String prompt = template.render(Map.of("TERMS", renderTerms(entries)));
        JsonNode payload = gemini.generateJson(prompt, schema, GeminiTimeout.QUIZ_GENERATE);

        // Ghép item Gemini trả về với từ trong sổ bằng chính field `term`. Deque vì hai
        // bản ghi khác pos vẫn có thể trùng term ("record" danh từ và động từ).
        Map<String, Deque<VocabEntry>> pending = new LinkedHashMap<>();
        for (VocabEntry entry : entries) {
            pending.computeIfAbsent(normalise(entry.getTerm()), key -> new ArrayDeque<>())
                   .add(entry);
        }

        Map<Long, QuizItem> built = new LinkedHashMap<>();
        for (JsonNode node : payload.path("items")) {
            Deque<VocabEntry> queue = pending.get(normalise(node.path("term").asText("")));
            if (queue == null || queue.isEmpty()) {
                log.warn("Gemini trả câu hỏi cho từ không nằm trong lô: '{}'",
                        node.path("term").asText(""));
                continue;
            }
            VocabEntry entry = queue.peek();
            Map<String, Object> itemPayload = toPayload(type, node);
            if (itemPayload == null) {
                // Loại TỪNG item hỏng rồi đi tiếp — khác DistractorValidator (loại cả bộ).
                // Người dùng đang đứng chờ; bắt họ đợi thêm một lượt Gemini vì một câu
                // hỏng là đắt vô lý, còn 9 câu kia vẫn dùng được.
                log.warn("Bỏ câu hỏi {} hỏng cho từ '{}'", type, entry.getTerm());
                continue;
            }
            queue.poll();
            built.put(entry.getId(), save(entry, type, itemPayload, promptVersion));
        }
        return built;
    }

    /** @return payload hợp lệ để lưu, hoặc null nếu item hỏng. */
    private Map<String, Object> toPayload(QuizType type, JsonNode node) {
        return switch (type) {
            case FILL_BLANK -> fillBlankPayload(node);
            case COLLOCATION_CHOICE -> collocationPayload(node);
            // FREE_WRITE không bao giờ đi qua Gemini lúc sinh đề.
            case FREE_WRITE -> null;
        };
    }

    private Map<String, Object> fillBlankPayload(JsonNode node) {
        String sentence = node.path("sentence").asText(null);
        String answer = node.path("answer").asText(null);
        String hint = node.path("hint").asText(null);
        if (!validator.isValidFillBlank(sentence, answer, hint)) {
            return null;
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("sentence", sentence);
        payload.put("answer", answer);
        payload.put("hint", hint);
        return payload;
    }

    private Map<String, Object> collocationPayload(JsonNode node) {
        List<String> options = new ArrayList<>();
        node.path("options").forEach(option -> options.add(option.asText(null)));
        Integer correctIndex = node.path("correct_index").isIntegralNumber()
                ? node.path("correct_index").asInt() : null;
        if (!validator.isValidCollocation(options, correctIndex)) {
            return null;
        }

        // Xáo ĐÚNG MỘT LẦN, ngay tại đây. Gemini có xu hướng đặt đáp án đúng ở vị trí 0
        // nên giữ nguyên thứ tự của nó là làm quiz đoán được mà không cần biết từ. Sau
        // dòng này thứ tự là bất biến: không xáo lúc dựng response, panel không xáo —
        // câu trả lời gửi lên là index trong CHÍNH mảng đang lưu ở đây.
        String correctOption = options.get(correctIndex);
        List<String> shuffled = new ArrayList<>(options);
        Collections.shuffle(shuffled, random);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("question", node.path("question").asText(""));
        payload.put("options", shuffled);
        payload.put("correct_index", shuffled.indexOf(correctOption));
        return payload;
    }

    private QuizItem save(VocabEntry entry, QuizType type, Map<String, Object> payload,
                          int promptVersion) {
        QuizItem item = new QuizItem();
        item.setVocabEntry(entry);
        item.setType(type);
        item.setPayload(payload);
        item.setPromptVersion(promptVersion);
        return items.save(item);
    }

    /** Mỗi từ một dòng: {@code term | pos | nghĩa tiếng Việt}. */
    private String renderTerms(List<VocabEntry> entries) {
        StringBuilder sb = new StringBuilder();
        for (VocabEntry entry : entries) {
            sb.append(nullToEmpty(entry.getTerm())).append(" | ")
              .append(nullToEmpty(entry.getPos())).append(" | ")
              .append(nullToEmpty(entry.getMeaningVi())).append('\n');
        }
        return sb.toString().trim();
    }

    private String normalise(String value) {
        return value == null ? "" : value.strip().toLowerCase(Locale.ROOT);
    }

    private String nullToEmpty(String value) {
        return value == null ? "" : value;
    }
}
