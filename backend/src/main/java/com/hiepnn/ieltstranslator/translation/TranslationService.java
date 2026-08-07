package com.hiepnn.ieltstranslator.translation;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiProperties;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
import com.hiepnn.ieltstranslator.translation.cache.LookupCache;
import com.hiepnn.ieltstranslator.translation.cache.LookupCacheRepository;
import com.hiepnn.ieltstranslator.translation.dto.TranslateRequest;
import com.hiepnn.ieltstranslator.translation.dto.TranslateResponse;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;
import java.util.Optional;

@Service
public class TranslationService {

    /** Giới hạn cứng phía server; content script cũng chặn ở cùng con số. */
    private static final int MAX_TEXT_LENGTH = 1500;

    private final LanguageDetector languageDetector;
    private final PromptLoader promptLoader;
    private final GeminiClient geminiClient;
    private final GeminiProperties geminiProperties;
    private final LookupCacheRepository cacheRepository;

    public TranslationService(LanguageDetector languageDetector,
                              PromptLoader promptLoader,
                              GeminiClient geminiClient,
                              GeminiProperties geminiProperties,
                              LookupCacheRepository cacheRepository) {
        this.languageDetector = languageDetector;
        this.promptLoader = promptLoader;
        this.geminiClient = geminiClient;
        this.geminiProperties = geminiProperties;
        this.cacheRepository = cacheRepository;
    }

    @Transactional
    public TranslateResponse translate(TranslateRequest request) {
        String text = request.text() == null ? "" : request.text().trim();
        if (text.length() > MAX_TEXT_LENGTH) {
            throw AppException.of(ErrorCode.TEXT_TOO_LONG,
                    "Đoạn bôi đen quá dài (tối đa " + MAX_TEXT_LENGTH + " ký tự)");
        }

        Direction direction = languageDetector.detect(text);
        Mode mode = Mode.of(text);
        PromptTemplate template = promptLoader.load(direction, mode);
        String context = request.contextSentence();
        String hash = cacheKey(text, context, direction, mode, template.version());

        Optional<LookupCache> cached = cacheRepository.findBySourceHash(hash);
        if (cached.isPresent()) {
            cacheRepository.incrementHitCount(cached.get().getId());
            return new TranslateResponse(direction, mode, true, cached.get().getResponse());
        }

        Map<String, Object> schema = TranslationSchemas.of(direction, mode);
        JsonNode payload = geminiClient.generateJson(template.render(text, context), schema,
                GeminiTimeout.TRANSLATE);

        cacheRepository.save(new LookupCache(hash, text, direction.name(), mode.name(),
                geminiProperties.model(), template.version(), payload));

        return new TranslateResponse(direction, mode, false, payload);
    }

    /** Cache key gồm: text + direction + mode + model + prompt_version (và context, để tránh
     *  đụng độ giữa các lượt tra cùng text nhưng khác ngữ cảnh). */
    private String cacheKey(String text, String context, Direction direction,
                            Mode mode, int promptVersion) {
        StringBuilder material = new StringBuilder();
        appendField(material, text);
        appendField(material, context);
        appendField(material, direction.name());
        appendField(material, mode.name());
        appendField(material, geminiProperties.model());
        appendField(material, String.valueOf(promptVersion));
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(material.toString().getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("JVM không có SHA-256", e);
        }
    }

    /**
     * Nối một field vào material dạng "độDài:nộiDung|" thay vì nối chuỗi trực tiếp có/không
     * dấu phân cách. Text và context là văn bản người dùng bôi đen tuỳ ý trên web, có thể
     * chứa bất kỳ ký tự nào (kể cả ký tự điều khiển do lỗi encoding khi paste) nên không thể
     * dựa vào giả định "ký tự phân cách này không bao giờ xuất hiện trong dữ liệu người dùng".
     * Tiền tố độ dài đảm bảo hai bộ input khác nhau — ví dụ ("ab","c") và ("a","bc") — không
     * bao giờ sinh ra cùng một chuỗi material, bất kể nội dung field chứa gì.
     */
    private static void appendField(StringBuilder sb, String value) {
        String safe = value == null ? "" : value;
        sb.append(safe.length()).append(':').append(safe).append('|');
    }
}
