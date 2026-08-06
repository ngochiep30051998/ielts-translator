package com.hiepnn.ieltstranslator.srs;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.vocabulary.VocabService;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabRequest;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.time.Duration;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class DistractorGeneratorIT extends AbstractPostgresIT {

    @Autowired VocabService vocabService;
    @Autowired SrsDistractorRepository distractors;
    @Autowired DistractorGenerator generator;
    @Autowired ObjectMapper objectMapper;
    @Autowired JdbcTemplate jdbc;

    @MockitoBean GeminiClient geminiClient;

    @BeforeEach
    void clean() {
        reset(geminiClient);
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM srs_distractor");
        jdbc.update("DELETE FROM vocab_entry");
    }

    private SaveVocabRequest request(String term, String pos) {
        return new SaveVocabRequest(term, term, "en", pos, null, "nghĩa của " + term,
                null, null, null, List.of(), null, null, null, null);
    }

    private void geminiReturnsValidSet() throws Exception {
        when(geminiClient.generateJson(anyString(), any(), any())).thenReturn(objectMapper.readTree("""
                {"vi_options": ["làm trầm trọng thêm", "phóng đại", "trì hoãn"],
                 "en_options": ["aggravate", "exaggerate", "postpone"]}
                """));
    }

    @Test
    @DisplayName("Lưu một từ đơn thì mồi nhử được sinh và lưu kèm prompt version")
    void generatesOnSave() throws Exception {
        geminiReturnsValidSet();

        SaveVocabResponse saved = vocabService.save(request("mitigate", "verb"));

        await().atMost(Duration.ofSeconds(5)).untilAsserted(() -> {
            SrsDistractor d = distractors.findByVocabEntry_Id(saved.id()).orElseThrow();
            assertThat(d.getViOptions()).hasSize(3);
            assertThat(d.getEnOptions()).containsExactly("aggravate", "exaggerate", "postpone");
            assertThat(d.getPromptVersion()).isEqualTo(generator.currentPromptVersion());
        });
    }

    @Test
    @DisplayName("Lưu cả một câu (pos = 'phrase') thì KHÔNG gọi Gemini")
    void skipsPhrase() throws Exception {
        geminiReturnsValidSet();

        vocabService.save(request("Governments must act on climate change.", "phrase"));

        Thread.sleep(300);
        verify(geminiClient, never()).generateJson(anyString(), any(), any());
        assertThat(distractors.count()).isZero();
    }

    @Test
    @DisplayName("Gemini lỗi thì từ vẫn nằm trong sổ, chỉ là chưa có mồi nhử")
    void geminiFailureDoesNotBreakSave() throws Exception {
        when(geminiClient.generateJson(anyString(), any(), any()))
                .thenThrow(AppException.of(ErrorCode.GEMINI_UNAVAILABLE, "Gemini chết"));

        SaveVocabResponse saved = vocabService.save(request("resilient", "adjective"));

        assertThat(saved.id()).isNotNull();
        Thread.sleep(500);
        assertThat(distractors.findByVocabEntry_Id(saved.id())).isEmpty();
    }

    @Test
    @DisplayName("Gemini trả bộ hỏng (trùng đáp án đúng) thì không lưu gì, để lần sau sinh lại")
    void rejectsInvalidSet() throws Exception {
        when(geminiClient.generateJson(anyString(), any(), any())).thenReturn(objectMapper.readTree("""
                {"vi_options": ["nghĩa của mitigate", "phóng đại", "trì hoãn"],
                 "en_options": ["aggravate", "exaggerate", "postpone"]}
                """));

        SaveVocabResponse saved = vocabService.save(request("mitigate", "verb"));

        Thread.sleep(500);
        assertThat(distractors.findByVocabEntry_Id(saved.id())).isEmpty();
    }

    @Test
    @DisplayName("Sinh lại cho từ đã có mồi nhử thì ghi đè, không tạo bản ghi thứ hai")
    void overwritesExisting() throws Exception {
        geminiReturnsValidSet();
        SaveVocabResponse saved = vocabService.save(request("mitigate", "verb"));
        await().atMost(Duration.ofSeconds(5))
               .until(() -> distractors.findByVocabEntry_Id(saved.id()).isPresent());

        when(geminiClient.generateJson(anyString(), any(), any())).thenReturn(objectMapper.readTree("""
                {"vi_options": ["một", "hai", "ba"],
                 "en_options": ["one", "two", "three"]}
                """));
        generator.generateAsync(saved.id());

        await().atMost(Duration.ofSeconds(5)).untilAsserted(() -> {
            assertThat(distractors.count()).isEqualTo(1L);
            assertThat(distractors.findByVocabEntry_Id(saved.id()).orElseThrow().getEnOptions())
                    .containsExactly("one", "two", "three");
        });
    }
}
