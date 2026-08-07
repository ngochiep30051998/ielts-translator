package com.hiepnn.ieltstranslator.translation;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.translation.cache.LookupCacheRepository;
import com.hiepnn.ieltstranslator.translation.dto.TranslateRequest;
import com.hiepnn.ieltstranslator.translation.dto.TranslateResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.util.Map;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class TranslationServiceIT extends AbstractPostgresIT {

    @Autowired TranslationService service;
    @Autowired LookupCacheRepository cacheRepository;
    @Autowired ObjectMapper objectMapper;

    @MockitoBean GeminiClient geminiClient;

    @BeforeEach
    void reset() {
        cacheRepository.deleteAll();
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenReturn(objectMapper.createObjectNode().put("meaning_vi", "tái tạo"));
    }

    @Test
    void englishWordRoutesToEnViWordMode() {
        TranslateResponse response = service.translate(
                new TranslateRequest("renewable", "We need renewable energy.", null, null));

        assertThat(response.direction()).isEqualTo(Direction.EN_VI);
        assertThat(response.mode()).isEqualTo(Mode.WORD);
        assertThat(response.cached()).isFalse();
        assertThat(response.payload().get("meaning_vi").asText()).isEqualTo("tái tạo");
    }

    @Test
    void vietnameseSentenceRoutesToViEnSentenceMode() {
        TranslateResponse response = service.translate(new TranslateRequest(
                "Chính phủ nên đầu tư nhiều hơn vào năng lượng tái tạo", null, null, null));

        assertThat(response.direction()).isEqualTo(Direction.VI_EN);
        assertThat(response.mode()).isEqualTo(Mode.SENTENCE);
    }

    @Test
    void firstCallHitsGeminiAndPersistsCache() {
        service.translate(new TranslateRequest("renewable", null, null, null));

        verify(geminiClient, times(1)).generateJson(anyString(), any(), any());
        assertThat(cacheRepository.count()).isEqualTo(1);
    }

    @Test
    void secondIdenticalCallServesFromCacheWithoutCallingGemini() {
        TranslateRequest request = new TranslateRequest("renewable", null, null, null);

        service.translate(request);
        clearInvocations(geminiClient);
        TranslateResponse second = service.translate(request);

        verifyNoInteractions(geminiClient);
        assertThat(second.cached()).isTrue();
        assertThat(second.payload().get("meaning_vi").asText()).isEqualTo("tái tạo");
        assertThat(cacheRepository.count()).isEqualTo(1);
    }

    @Test
    void cacheHitIncrementsHitCount() {
        TranslateRequest request = new TranslateRequest("renewable", null, null, null);
        service.translate(request);
        service.translate(request);
        service.translate(request);

        assertThat(cacheRepository.findAll().get(0).getHitCount()).isEqualTo(2);
    }

    @Test
    void differentContextDoesNotShareCacheEntry() {
        service.translate(new TranslateRequest("renewable", "context A", null, null));
        service.translate(new TranslateRequest("renewable", "context B", null, null));

        assertThat(cacheRepository.count()).isEqualTo(2);
    }

    @Test
    void textOverLimitIsRejected() {
        String tooLong = "a".repeat(1501);

        assertThatThrownBy(() -> service.translate(new TranslateRequest(tooLong, null, null, null)))
                .isInstanceOf(com.hiepnn.ieltstranslator.common.AppException.class)
                .satisfies(ex -> assertThat(
                        ((com.hiepnn.ieltstranslator.common.AppException) ex).code())
                        .isEqualTo(com.hiepnn.ieltstranslator.common.ErrorCode.TEXT_TOO_LONG));

        verifyNoInteractions(geminiClient);
    }

    @Test
    void geminiIsCalledWithSchemaMatchingDetectedRoute() {
        service.translate(new TranslateRequest("renewable", null, null, null));

        verify(geminiClient).generateJson(anyString(),
                eq(TranslationSchemas.of(Direction.EN_VI, Mode.WORD)),
                eq(com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout.TRANSLATE));
    }

    @Test
    void promptSentToGeminiContainsTheSelectedText() {
        service.translate(new TranslateRequest("renewable", "some context", null, null));

        verify(geminiClient).generateJson(
                argThat(prompt -> prompt.contains("renewable") && prompt.contains("some context")),
                any(), any());
    }

    @Test
    void cacheKeyDoesNotCollideWhenTextAndContextBoundaryShifts() {
        service.translate(new TranslateRequest("ab", "c", null, null));
        service.translate(new TranslateRequest("a", "bc", null, null));

        assertThat(cacheRepository.count()).isEqualTo(2);
    }
}
