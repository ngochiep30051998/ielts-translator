package com.hiepnn.ieltstranslator.auth;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
public class GoogleConfig {

    /**
     * Ngắn hơn hẳn Gemini vì đây là một lượt đổi token, không phải sinh văn bản: Google trả
     * trong vài trăm ms hoặc là hỏng. Chờ 30 giây chỉ làm người dùng nhìn màn đăng nhập
     * treo lâu hơn trước khi nhận đúng cái lỗi đó.
     */
    private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(5);
    private static final Duration READ_TIMEOUT = Duration.ofSeconds(10);

    @Bean("googleRestClient")
    public RestClient googleRestClient(AuthProperties props) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(CONNECT_TIMEOUT);
        factory.setReadTimeout(READ_TIMEOUT);
        return RestClient.builder()
                .requestFactory(factory)
                .baseUrl(props.googleTokenUrl())
                .build();
    }
}
