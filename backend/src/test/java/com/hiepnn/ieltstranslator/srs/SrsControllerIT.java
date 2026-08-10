package com.hiepnn.ieltstranslator.srs;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDate;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@AutoConfigureMockMvc
class SrsControllerIT extends AbstractPostgresIT {

    @Autowired MockMvc mockMvc;
    @Autowired SrsCardRepository cards;
    @Autowired VocabEntryRepository vocab;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    // Từ khi SrsService.due() bắn sinh mồi nhử nền cho thẻ còn thiếu, mọi lần gọi
    // /api/srs/due đều kéo theo một lượt gọi Gemini. Mock để test không phụ thuộc mạng.
    @MockitoBean GeminiClient geminiClient;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM srs_distractor");
        jdbc.update("DELETE FROM vocab_entry");
    }

    private SrsCard seed() {
        VocabEntry e = new VocabEntry();
        // user_id là NOT NULL từ V6 — dựng entry mà quên chủ sở hữu là nổ lúc insert.
        e.setUser(ownerUser());
        e.setTerm("mitigate");
        e.setLemma("mitigate");
        e.setLang("en");
        e.setPos("verb");
        e.setIpa("/ˈmɪtɪgeɪt/");
        e.setMeaningVi("giảm nhẹ");
        e.setCollocations(objectMapper.createArrayNode());
        e.setExamples(objectMapper.createArrayNode());
        vocab.saveAndFlush(e);

        SrsCard c = new SrsCard();
        c.setVocabEntry(e);
        c.setDueDate(LocalDate.now());
        c.setState(CardState.NEW);
        return cards.saveAndFlush(c);
    }

    @Test
    @DisplayName("GET /api/srs/due trả thẻ kèm dữ liệu vocab đã gộp sẵn")
    void due() throws Exception {
        seed();

        mockMvc.perform(get("/api/srs/due").header("Authorization", BEARER_OWNER).param("limit", "50").param("newLimit", "30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].term").value("mitigate"))
                .andExpect(jsonPath("$[0].meaningVi").value("giảm nhẹ"))
                .andExpect(jsonPath("$[0].ipa").value("/ˈmɪtɪgeɪt/"))
                .andExpect(jsonPath("$[0].state").value("NEW"))
                .andExpect(jsonPath("$[0].vocabEntryId").isNumber())
                // Extension khai dueDate kiểu string. Nếu ai đó bật
                // WRITE_DATES_AS_TIMESTAMPS thì LocalDate ra mảng [2026,8,6] và phía
                // kia vỡ IM LẶNG — isString() là cái chặn duy nhất bắt được việc đó.
                .andExpect(jsonPath("$[0].dueDate").isString())
                .andExpect(jsonPath("$[0].dueDate").value(LocalDate.now().toString()));
    }

    @Test
    @DisplayName("GET /api/srs/stats trả ba con số")
    void stats() throws Exception {
        seed();

        mockMvc.perform(get("/api/srs/stats").header("Authorization", BEARER_OWNER).param("newLimit", "30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.dueCount").value(1))
                .andExpect(jsonPath("$.newCount").value(1))
                .andExpect(jsonPath("$.learnedCount").value(0));
    }

    @Test
    @DisplayName("POST /api/srs/review trả lịch kế tiếp")
    void review() throws Exception {
        SrsCard c = seed();

        mockMvc.perform(post("/api/srs/review").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cardId\":" + c.getId() + ",\"rating\":\"GOOD\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.intervalDays").value(1))
                .andExpect(jsonPath("$.nextDueDate").isString())
                .andExpect(jsonPath("$.nextDueDate").value(LocalDate.now().plusDays(1).toString()))
                .andExpect(jsonPath("$.easeFactor").value(2.5));
    }

    @Test
    @DisplayName("POST /api/srs/review với thẻ lạ trả 404 đúng hình dạng lỗi chung")
    void reviewNotFound() throws Exception {
        mockMvc.perform(post("/api/srs/review").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cardId\":999999,\"rating\":\"GOOD\"}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"))
                .andExpect(jsonPath("$.retryable").value(false))
                .andExpect(jsonPath("$.message").isString());
    }

    @Test
    @DisplayName("POST /api/srs/review thiếu rating trả 400")
    void reviewValidation() throws Exception {
        mockMvc.perform(post("/api/srs/review").header("Authorization", BEARER_OWNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cardId\":1}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("CardDto có hai mảng mồi nhử, rỗng khi chưa sinh")
    void cardDtoCarriesEmptyDistractorsWhenNotGenerated() throws Exception {
        seed();

        mockMvc.perform(get("/api/srs/due").header("Authorization", BEARER_OWNER).param("limit", "10").param("newLimit", "30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].viDistractors").isArray())
                .andExpect(jsonPath("$[0].viDistractors").isEmpty())
                .andExpect(jsonPath("$[0].enDistractors").isArray())
                .andExpect(jsonPath("$[0].enDistractors").isEmpty());
    }
}
