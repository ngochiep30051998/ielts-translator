package com.hiepnn.ieltstranslator.common.gemini;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "gemini")
public record GeminiProperties(
        String apiKey,
        String model,
        String baseUrl,
        int timeoutSeconds,
        int quizGenerateTimeoutSeconds,
        int quizGradeTimeoutSeconds,
        long retryBackoffMillis
) {}
