package com.hiepnn.ieltstranslator.common.gemini;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.EnumMap;
import java.util.Map;

@Configuration
public class GeminiConfig {

    /** Bắt tay TCP không phụ thuộc độ dài output nên dùng chung cho cả ba mức. */
    private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(5);

    /**
     * Một RestClient cho mỗi mức timeout. Read-timeout được nướng vào request factory nên
     * không đổi được sau khi client đã dựng — đó là lý do phải có ba client chứ không phải
     * một client và một tham số.
     *
     * <p>Không cần {@code @Qualifier}: Spring chỉ coi một tham số {@code Map} là "gom mọi
     * bean theo tên" khi khoá là {@code String} (DefaultListableBeanFactory
     * .resolveMultipleBeanMap trả null ngay nếu khoá khác String). Khoá ở đây là enum nên
     * map này được phân giải như một bean thường. Đổi khoá sang String mới là chỗ hỏng.
     */
    @Bean
    public Map<GeminiTimeout, RestClient> geminiRestClients(GeminiProperties props) {
        Map<GeminiTimeout, RestClient> clients = new EnumMap<>(GeminiTimeout.class);
        clients.put(GeminiTimeout.TRANSLATE, build(props, props.timeoutSeconds()));
        clients.put(GeminiTimeout.QUIZ_GENERATE, build(props, props.quizGenerateTimeoutSeconds()));
        clients.put(GeminiTimeout.QUIZ_GRADE, build(props, props.quizGradeTimeoutSeconds()));
        return clients;
    }

    private RestClient build(GeminiProperties props, int readTimeoutSeconds) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(CONNECT_TIMEOUT);
        factory.setReadTimeout(Duration.ofSeconds(readTimeoutSeconds));
        return RestClient.builder()
                .requestFactory(factory)
                .baseUrl(props.baseUrl())
                .build();
    }
}
