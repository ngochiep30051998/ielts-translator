package com.hiepnn.ieltstranslator.common.gemini;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
public class GeminiConfig {

    @Bean
    public RestClient geminiRestClient(GeminiProperties props) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(5));
        factory.setReadTimeout(Duration.ofSeconds(props.timeoutSeconds()));
        return RestClient.builder()
                .requestFactory(factory)
                .baseUrl(props.baseUrl())
                .build();
    }
}
