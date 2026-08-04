package com.hiepnn.ieltstranslator.translation;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.translation.cache.LookupCacheRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@AutoConfigureMockMvc
class TranslateControllerIT extends AbstractPostgresIT {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper objectMapper;
    @Autowired LookupCacheRepository cacheRepository;

    @MockitoBean GeminiClient geminiClient;

    @BeforeEach
    void reset() {
        cacheRepository.deleteAll();
    }

    @Test
    void returnsDirectionModeAndPayload() throws Exception {
        when(geminiClient.generateJson(anyString(), any()))
                .thenReturn(objectMapper.createObjectNode().put("meaning_vi", "tái tạo"));

        mockMvc.perform(post("/api/translate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                 {"text":"renewable","contextSentence":"We need renewable energy."}
                                 """))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.direction").value("EN_VI"))
               .andExpect(jsonPath("$.mode").value("WORD"))
               .andExpect(jsonPath("$.cached").value(false))
               .andExpect(jsonPath("$.payload.meaning_vi").value("tái tạo"));
    }

    @Test
    void quotaErrorReturns429WithErrorShape() throws Exception {
        when(geminiClient.generateJson(anyString(), any()))
                .thenThrow(AppException.of(ErrorCode.GEMINI_QUOTA, "Đã hết quota Gemini"));

        mockMvc.perform(post("/api/translate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"text\":\"renewable\"}"))
               .andExpect(status().isTooManyRequests())
               .andExpect(jsonPath("$.code").value("GEMINI_QUOTA"))
               .andExpect(jsonPath("$.retryable").value(false))
               .andExpect(jsonPath("$.message").isNotEmpty());
    }

    @Test
    void unavailableErrorReturns503AndIsMarkedRetryable() throws Exception {
        when(geminiClient.generateJson(anyString(), any()))
                .thenThrow(AppException.of(ErrorCode.GEMINI_UNAVAILABLE, "Gemini không phản hồi kịp"));

        mockMvc.perform(post("/api/translate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"text\":\"renewable\"}"))
               .andExpect(status().isServiceUnavailable())
               .andExpect(jsonPath("$.code").value("GEMINI_UNAVAILABLE"))
               .andExpect(jsonPath("$.retryable").value(true));
    }

    @Test
    void textOverLimitReturns400() throws Exception {
        String tooLong = "a".repeat(1501);

        mockMvc.perform(post("/api/translate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                java.util.Map.of("text", tooLong))))
               .andExpect(status().isBadRequest())
               .andExpect(jsonPath("$.code").value("TEXT_TOO_LONG"));
    }

    @Test
    void blankTextFailsValidationWith400() throws Exception {
        mockMvc.perform(post("/api/translate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"text\":\"   \"}"))
               .andExpect(status().isBadRequest())
               .andExpect(jsonPath("$.code").value("INTERNAL"))
               .andExpect(jsonPath("$.retryable").value(false));
    }
}
