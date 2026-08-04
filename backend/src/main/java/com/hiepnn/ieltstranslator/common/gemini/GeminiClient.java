package com.hiepnn.ieltstranslator.common.gemini;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.util.List;
import java.util.Map;

@Component
public class GeminiClient {

    private static final Logger log = LoggerFactory.getLogger(GeminiClient.class);
    private static final int MAX_ATTEMPTS = 2;

    private final RestClient restClient;
    private final GeminiProperties props;
    private final ObjectMapper objectMapper;

    public GeminiClient(RestClient geminiRestClient, GeminiProperties props, ObjectMapper objectMapper) {
        this.restClient = geminiRestClient;
        this.props = props;
        this.objectMapper = objectMapper;
    }

    /**
     * Gọi Gemini với structured output. Chỉ retry lỗi tạm thời (5xx, timeout,
     * JSON hỏng) đúng 1 lần. Lỗi quota không retry.
     */
    public JsonNode generateJson(String prompt, Map<String, Object> responseSchema) {
        AppException last = null;
        for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
            try {
                return callOnce(prompt, responseSchema);
            } catch (AppException ex) {
                // Chỉ retry lỗi tạm thời (server tạm ngưng, JSON hỏng do model trả sai định
                // dạng). Liệt kê "được retry" thay vì "không được retry" để an toàn hơn khi
                // sau này thêm ErrorCode mới — mặc định không retry trừ khi biết chắc là tạm thời.
                boolean transientFailure = ex.code() == ErrorCode.GEMINI_UNAVAILABLE
                        || ex.code() == ErrorCode.PARSE_ERROR;
                if (!transientFailure) {
                    throw ex;
                }
                last = ex;
                log.warn("Gemini lần {} thất bại ({}), {}", attempt, ex.code(),
                        attempt < MAX_ATTEMPTS ? "thử lại" : "bỏ cuộc");
                if (attempt < MAX_ATTEMPTS) {
                    sleepBackoff();
                }
            }
        }
        throw last;
    }

    private JsonNode callOnce(String prompt, Map<String, Object> responseSchema) {
        Map<String, Object> body = Map.of(
                "contents", List.of(Map.of("role", "user",
                        "parts", List.of(Map.of("text", prompt)))),
                "generationConfig", Map.of(
                        "responseMimeType", "application/json",
                        "responseSchema", responseSchema));

        ResponseEntity<String> response;
        try {
            response = restClient.post()
                    .uri(uri -> uri.path("/v1beta/models/{model}:generateContent")
                            .queryParam("key", props.apiKey())
                            .build(props.model()))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .onStatus(status -> true, (req, res) -> { /* xử lý thủ công bên dưới */ })
                    .toEntity(String.class);
        } catch (RestClientException ex) {
            // Timeout đọc socket thường không lộ ra như ResourceAccessException ở đây: vì có
            // onStatus no-op ở trên, RestClient đọc status code trước (lần đọc đầu tiên time
            // out), rồi lại đọc header/content-type khi trích xuất body (lần đọc thứ hai ném
            // SocketTimeoutException thô), Spring bọc nó thành RestClientException chung chung
            // thay vì ResourceAccessException. Bắt RestClientException (cha của
            // ResourceAccessException) để phủ cả hai trường hợp mất kết nối/timeout.
            //
            // Bắt rộng như vậy chỉ an toàn với 2 tiền đề ở trên: (1) onStatus(status -> true, ...)
            // luôn đăng ký và luôn khớp mọi status TRƯỚC default handler, nên không có
            // HttpClientErrorException/HttpServerErrorException nào thoát ra ngoài khối try này;
            // (2) kiểu đích luôn là String.class, không có converter phức tạp nào khác có thể
            // ném lỗi nghiệp vụ. Nếu sau này một trong hai thay đổi (bỏ onStatus, hoặc đổi kiểu
            // đích), catch rộng này có thể nuốt nhầm RestClientResponseException và che mất lỗi
            // HTTP thật — cần thu hẹp lại catch khi đó.
            throw AppException.of(ErrorCode.GEMINI_UNAVAILABLE, "Gemini không phản hồi kịp");
        }

        int status = response.getStatusCode().value();
        if (status == 429) {
            throw AppException.of(ErrorCode.GEMINI_QUOTA, "Đã hết quota Gemini");
        }
        if (status >= 500) {
            throw AppException.of(ErrorCode.GEMINI_UNAVAILABLE, "Gemini trả lỗi HTTP " + status);
        }
        if (status >= 400) {
            // Lỗi cấu hình phía ta (key sai, model sai) — retry không bao giờ cứu được, nên
            // KHÔNG map vào GEMINI_UNAVAILABLE (sẽ bị coi là retryable và bị retry vô ích).
            throw AppException.of(ErrorCode.INTERNAL,
                    "Gemini từ chối request (HTTP " + status + "). Kiểm tra GEMINI_API_KEY và GEMINI_MODEL trong file .env.");
        }
        return extractPayload(response.getBody());
    }

    private JsonNode extractPayload(String rawBody) {
        try {
            JsonNode root = objectMapper.readTree(rawBody);
            JsonNode candidates = root.path("candidates");
            if (!candidates.isArray() || candidates.isEmpty()) {
                throw AppException.of(ErrorCode.PARSE_ERROR, "Gemini không trả candidate nào");
            }
            String inner = candidates.get(0).path("content").path("parts").path(0).path("text").asText(null);
            if (inner == null) {
                throw AppException.of(ErrorCode.PARSE_ERROR, "Gemini trả candidate rỗng");
            }
            return objectMapper.readTree(inner);
        } catch (AppException ex) {
            throw ex;
        } catch (Exception ex) {
            throw AppException.of(ErrorCode.PARSE_ERROR, "Không đọc được JSON từ Gemini");
        }
    }

    private void sleepBackoff() {
        try {
            Thread.sleep(props.retryBackoffMillis());
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        }
    }
}
