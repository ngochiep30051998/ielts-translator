package com.hiepnn.ieltstranslator.srs;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
import com.hiepnn.ieltstranslator.translation.PromptLoader;
import com.hiepnn.ieltstranslator.translation.PromptTemplate;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntrySavedEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Sinh mồi nhử cho câu trắc nghiệm ôn tập.
 *
 * <p>Vì sao KHÔNG gộp vào {@link SrsCardCreator}: creator chạy đồng bộ trong cùng
 * transaction với lệnh lưu từ. Gọi Gemini ở đó sẽ làm thao tác lưu treo tới 15 giây, và
 * Gemini lỗi sẽ rollback cả việc lưu từ. Ở đây phải là AFTER_COMMIT (từ đã nằm chắc
 * trong sổ trước khi gọi mạng) và {@code @Async} (response không chờ Gemini).
 */
@Component
public class DistractorGenerator {

    private static final Logger log = LoggerFactory.getLogger(DistractorGenerator.class);

    /** pos của một câu đầy đủ — câu không làm trắc nghiệm được. */
    private static final String PHRASE_POS = "phrase";
    private static final String PROMPT_FILE = "srs-distractors.md";

    private static final Map<String, Object> SCHEMA = Map.of(
            "type", "object",
            "properties", Map.of(
                    "vi_options", Map.of("type", "array", "items", Map.of("type", "string")),
                    "en_options", Map.of("type", "array", "items", Map.of("type", "string"))),
            "required", List.of("vi_options", "en_options"));

    /** Chặn xếp chồng call cho cùng một từ khi người dùng mở tab ôn nhiều lần. */
    private final Set<Long> inFlight = ConcurrentHashMap.newKeySet();

    private final VocabEntryRepository vocab;
    private final SrsDistractorRepository distractors;
    private final DistractorValidator validator;
    private final GeminiClient gemini;
    private final PromptLoader prompts;

    public DistractorGenerator(VocabEntryRepository vocab, SrsDistractorRepository distractors,
                               DistractorValidator validator, GeminiClient gemini,
                               PromptLoader prompts) {
        this.vocab = vocab;
        this.distractors = distractors;
        this.validator = validator;
        this.gemini = gemini;
        this.prompts = prompts;
    }

    public int currentPromptVersion() {
        return prompts.load(PROMPT_FILE).version();
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Async("srsTaskExecutor")
    public void onVocabEntrySaved(VocabEntrySavedEvent event) {
        generate(event.entry().getId());
    }

    /** Bù mồi nhử cho từ cũ hoặc cho lần Gemini hỏng. Gọi từ bean khác nên proxy @Async có tác dụng. */
    @Async("srsTaskExecutor")
    public void generateAsync(Long vocabEntryId) {
        generate(vocabEntryId);
    }

    private void generate(Long vocabEntryId) {
        if (vocabEntryId == null || !inFlight.add(vocabEntryId)) {
            return;
        }
        try {
            vocab.findById(vocabEntryId).ifPresent(this::generateFor);
        } catch (RuntimeException ex) {
            // Không ai đang đứng chờ việc này — log rồi thôi, lần mở tab ôn sau sẽ thử lại.
            log.warn("Không sinh được mồi nhử cho vocab id={}: {}", vocabEntryId, ex.toString());
        } finally {
            inFlight.remove(vocabEntryId);
        }
    }

    private void generateFor(VocabEntry entry) {
        if (PHRASE_POS.equals(entry.getPos())) {
            return;
        }

        PromptTemplate template = prompts.load(PROMPT_FILE);
        String prompt = template.render(Map.of(
                "TERM", nullToEmpty(entry.getTerm()),
                "POS", nullToEmpty(entry.getPos()),
                "MEANING_VI", nullToEmpty(entry.getMeaningVi()),
                "DEFINITION_EN", nullToEmpty(entry.getDefinitionEn())));

        // TRANSLATE (15s) chứ không phải QUIZ_GENERATE: đây là call nhỏ chạy @Async, không
        // ai đứng chờ. Khác mức với quiz cũng là thứ cho phép test quiz đếm call bằng
        // eq(GeminiTimeout.QUIZ_GENERATE) mà không lẫn với luồng sinh mồi nhử chạy nền.
        JsonNode payload = gemini.generateJson(prompt, SCHEMA, GeminiTimeout.TRANSLATE);
        DistractorSet set = new DistractorSet(
                readStrings(payload.path("vi_options")),
                readStrings(payload.path("en_options")));

        if (!validator.isValid(set, entry.getMeaningVi(), entry.getTerm())) {
            log.warn("Gemini trả bộ mồi nhử không hợp lệ cho '{}', bỏ qua", entry.getTerm());
            return;
        }

        SrsDistractor row = distractors.findByVocabEntry_Id(entry.getId())
                .orElseGet(SrsDistractor::new);
        row.setVocabEntry(entry);
        row.setViOptions(set.viOptions());
        row.setEnOptions(set.enOptions());
        row.setPromptVersion(template.version());
        distractors.save(row);
    }

    private List<String> readStrings(JsonNode array) {
        if (!array.isArray()) {
            return List.of();
        }
        List<String> out = new ArrayList<>(array.size());
        array.forEach(node -> out.add(node.asText(null)));
        return out;
    }

    private String nullToEmpty(String value) {
        return value == null ? "" : value;
    }
}
