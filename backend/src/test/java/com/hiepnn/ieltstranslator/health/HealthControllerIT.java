package com.hiepnn.ieltstranslator.health;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
class HealthControllerIT {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        registry.add("gemini.api-key", () -> "test-key");
    }

    @Autowired
    MockMvc mockMvc;

    @Test
    void healthReportsDbAndGeminiConfigured() throws Exception {
        mockMvc.perform(get("/api/health"))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.status").value("UP"))
               .andExpect(jsonPath("$.dbConnected").value(true))
               .andExpect(jsonPath("$.geminiConfigured").value(true));
    }
}
