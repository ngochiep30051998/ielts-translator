package com.hiepnn.ieltstranslator;

import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@Testcontainers
public abstract class AbstractPostgresIT {

    @ServiceConnection
    static final PostgreSQLContainer<?> POSTGRES =
            new PostgreSQLContainer<>("postgres:16-alpine");

    static {
        POSTGRES.start();   // dùng chung một container cho mọi test class
    }

    @DynamicPropertySource
    static void defaultProps(DynamicPropertyRegistry registry) {
        registry.add("gemini.api-key", () -> "test-key");
        registry.add("gemini.retry-backoff-millis", () -> 10L);
        // Cổng chết trên loopback: mọi đường gọi Gemini KHÔNG được mock (ví dụ
        // DistractorGenerator chạy nền khi test lưu từ) sẽ bị connection refused ngay
        // lập tức, thay vì bay ra generativelanguage.googleapis.com thật bằng "test-key".
        // Không có test nào được phép phụ thuộc mạng; test cần Gemini thì @MockitoBean nó.
        registry.add("gemini.base-url", () -> "http://127.0.0.1:1");
    }
}
