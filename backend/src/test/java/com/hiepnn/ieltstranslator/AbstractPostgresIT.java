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
    }
}
