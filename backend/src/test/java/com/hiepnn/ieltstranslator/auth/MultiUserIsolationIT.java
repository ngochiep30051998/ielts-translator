package com.hiepnn.ieltstranslator.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Hai người dùng, dữ liệu TRÙNG TÊN (cả hai cùng lưu từ "mitigate").
 *
 * <p>Trùng tên là cố ý: nó bắt được ca truy vấn tìm theo term mà quên lọc user — thứ mà dữ
 * liệu khác nhau sẽ giấu đi hoàn toàn.
 *
 * <p><b>Luật:</b> endpoint mới KHÔNG có mặt trong file này là endpoint chưa được chứng minh
 * an toàn. Quên một mệnh đề {@code WHERE user_id = ?} không làm gì đỏ cả — nó chỉ lặng lẽ
 * cho người này đọc dữ liệu người kia.
 */
@AutoConfigureMockMvc
class MultiUserIsolationIT extends AbstractPostgresIT {

    private static final String SECOND_EMAIL = "second@test.local";

    @Autowired MockMvc mockMvc;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    @MockitoBean GeminiClient geminiClient;

    private String tokenA;
    private String tokenB;
    private Long idA;
    private Long idB;
    private long vocabA;
    private long vocabB;

    @BeforeEach
    void seedTwoUsers() {
        reset(geminiClient);
        jdbc.update("DELETE FROM quiz_attempt");
        jdbc.update("DELETE FROM quiz_item");
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM srs_distractor");
        jdbc.update("DELETE FROM vocab_entry");

        idA = ownerId();
        idB = userId(SECOND_EMAIL);
        tokenA = BEARER_OWNER.substring("Bearer ".length());
        tokenB = tokenFor(idB);

        vocabA = seedWord(idA, "mitigate", "giảm nhẹ (của A)");
        vocabB = seedWord(idB, "mitigate", "giảm nhẹ (của B)");
    }

    /** Một từ đã ôn — đủ điều kiện vào cả hàng đợi SRS lẫn danh sách ứng viên quiz. */
    private long seedWord(Long userId, String term, String meaning) {
        Long id = jdbc.queryForObject("""
                INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id)
                VALUES (?, ?, 'en', 'verb', ?, ?) RETURNING id""",
                Long.class, term, term, meaning, userId);
        jdbc.update("""
                INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses)
                VALUES (?, CURRENT_DATE, 'REVIEW', 3, 1)""", id);
        return id;
    }

    private long cardOf(long vocabId) {
        return jdbc.queryForObject(
                "SELECT id FROM srs_card WHERE vocab_entry_id = ?", Long.class, vocabId);
    }

    private String bearer(String token) {
        return "Bearer " + token;
    }

    /* ---------- vocabulary ---------- */

    @Test
    @DisplayName("GET /api/vocab chỉ trả sổ từ của chính mình — kể cả totalElements")
    void vocabListIsScoped() throws Exception {
        // totalElements đến từ countQuery riêng. Quên user_id ở đó thì danh sách đúng nhưng
        // con số lộ kích thước sổ từ của người khác.
        mockMvc.perform(get("/api/vocab").header("Authorization", bearer(tokenA)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalElements").value(1))
                .andExpect(jsonPath("$.content[0].meaningVi").value("giảm nhẹ (của A)"));

        mockMvc.perform(get("/api/vocab").header("Authorization", bearer(tokenB)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalElements").value(1))
                .andExpect(jsonPath("$.content[0].meaningVi").value("giảm nhẹ (của B)"));
    }

    @Test
    @DisplayName("GET /api/vocab/{id} của người khác → 404, KHÔNG phải 403")
    void readingOthersEntryIsNotFound() throws Exception {
        // 404 chứ không 403: 403 xác nhận "id này có tồn tại", tức là một kênh dò id.
        mockMvc.perform(get("/api/vocab/" + vocabB).header("Authorization", bearer(tokenA)))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("DELETE /api/vocab/{id} của người khác → 404 và hàng đó VẪN CÒN")
    void deletingOthersEntryDoesNothing() throws Exception {
        mockMvc.perform(delete("/api/vocab/" + vocabB).header("Authorization", bearer(tokenA)))
                .andExpect(status().isNotFound());

        // Kiểm cả status LẪN dữ liệu: trả 404 mà vẫn xoá là ca tệ nhất và im lặng nhất.
        Integer left = jdbc.queryForObject(
                "SELECT count(*) FROM vocab_entry WHERE id = ?", Integer.class, vocabB);
        assertThat(left).isEqualTo(1);
    }

    @Test
    @DisplayName("export.csv chỉ chứa từ của mình")
    void exportIsScoped() throws Exception {
        mockMvc.perform(get("/api/vocab/export.csv").header("Authorization", bearer(tokenA)))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("giảm nhẹ (của A)")));
        mockMvc.perform(get("/api/vocab/export.csv").header("Authorization", bearer(tokenA)))
                .andExpect(content().string(org.hamcrest.Matchers.not(
                        org.hamcrest.Matchers.containsString("giảm nhẹ (của B)"))));
    }

    @Test
    @DisplayName("Hai người cùng lưu 'mitigate' đều được — UNIQUE nay theo user")
    void sameTermForTwoUsersIsAllowed() {
        // Chính là ràng buộc mà V6 đổi. Nếu ai đó khôi phục uq_vocab_term_pos toàn cục thì
        // seedTwoUsers() ở trên đã nổ trước khi tới đây.
        assertThat(vocabA).isNotEqualTo(vocabB);
    }

    /* ---------- srs ---------- */

    @Test
    @DisplayName("GET /api/srs/due và /stats chỉ đếm thẻ của mình")
    void srsIsScoped() throws Exception {
        mockMvc.perform(get("/api/srs/due").header("Authorization", bearer(tokenA)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1));
        mockMvc.perform(get("/api/srs/stats").header("Authorization", bearer(tokenA)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.dueCount").value(1));
    }

    @Test
    @DisplayName("POST /api/srs/review với cardId của người khác → 404 và lịch KHÔNG đổi")
    void reviewingOthersCardIsRejected() throws Exception {
        long cardB = cardOf(vocabB);
        String before = jdbc.queryForObject(
                "SELECT due_date::text FROM srs_card WHERE id = ?", String.class, cardB);

        mockMvc.perform(post("/api/srs/review")
                        .header("Authorization", bearer(tokenA))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cardId\":%d,\"rating\":\"GOOD\"}".formatted(cardB)))
                .andExpect(status().isNotFound());

        String after = jdbc.queryForObject(
                "SELECT due_date::text FROM srs_card WHERE id = ?", String.class, cardB);
        assertThat(after).isEqualTo(before);
    }

    /* ---------- quiz ---------- */

    @Test
    @DisplayName("POST /api/quiz/generate với vocabIds của người khác → không sinh đề nào")
    void generateWithForeignVocabIdsYieldsNothing() throws Exception {
        // vocabIds đến THẲNG từ client. Đây là lỗ IDOR rõ nhất của cả hệ thống: đề sinh ra
        // sẽ chứa term và câu ví dụ lấy từ sổ từ của người khác.
        mockMvc.perform(post("/api/quiz/generate")
                        .header("Authorization", bearer(tokenA))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"vocabIds\":[%d],\"type\":\"FREE_WRITE\"}".formatted(vocabB)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));

        // Và không đốt quota Gemini cho một request đang cố đọc dữ liệu người khác.
        verify(geminiClient, never()).generateJson(anyString(), any(), any());
    }

    @Test
    @DisplayName("POST /api/quiz/answer với quizItemId của người khác → 404")
    void answeringOthersItemIsRejected() throws Exception {
        long itemB = seedFreeWriteItem(vocabB);

        mockMvc.perform(post("/api/quiz/answer")
                        .header("Authorization", bearer(tokenA))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":%d,\"answer\":\"\"}".formatted(itemB)))
                .andExpect(status().isNotFound());

        Integer attempts = jdbc.queryForObject(
                "SELECT count(*) FROM quiz_attempt WHERE quiz_item_id = ?", Integer.class, itemB);
        assertThat(attempts).isZero();
    }

    @Test
    @DisplayName("POST /api/quiz/explain với item của người khác → 404 và KHÔNG gọi Gemini")
    void explainingOthersItemIsRejected() throws Exception {
        long itemB = seedFreeWriteItem(vocabB);
        // B đã trả lời rồi, nên 404 ở đây KHÔNG thể do "chưa có lượt làm".
        jdbc.update("""
                INSERT INTO quiz_attempt (quiz_item_id, user_answer, correct, score)
                VALUES (?, 'we mitigate it', true, 90)""", itemB);

        mockMvc.perform(post("/api/quiz/explain")
                        .header("Authorization", bearer(tokenA))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"quizItemId\":%d}".formatted(itemB)))
                .andExpect(status().isNotFound());

        // /explain TIẾT LỘ ĐÁP ÁN — rò ở đây vừa là rò dữ liệu vừa là đốt quota của B.
        verify(geminiClient, never()).generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE));
    }

    private long seedFreeWriteItem(long vocabId) {
        return jdbc.queryForObject("""
                INSERT INTO quiz_item (vocab_entry_id, type, payload, prompt_version)
                VALUES (?, 'FREE_WRITE', '{"question":"Viết một câu"}'::jsonb, 1)
                RETURNING id""", Long.class, vocabId);
    }

    /* ---------- ngoại lệ có chủ ý ---------- */

    @Test
    @DisplayName("lookup_cache CỐ Ý dùng chung — B ăn cache của A và đó là tính năng")
    void lookupCacheIsSharedOnPurpose() throws Exception {
        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.TRANSLATE)))
                .thenReturn(objectMapper.readTree(
                        "{\"term\":\"mitigate\",\"meaning_vi\":\"giảm nhẹ\",\"pos\":\"verb\"}"));

        mockMvc.perform(post("/api/translate")
                        .header("Authorization", bearer(tokenA))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"text\":\"mitigate\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cached").value(false));

        // Bất biến NGƯỢC CHIỀU mọi test còn lại, nên phải viết ra: bản dịch của một chuỗi
        // công khai không phải dữ liệu cá nhân, và dùng chung là phần tiết kiệm quota
        // Gemini lớn nhất của hệ thống. Ai đó "sửa cho nhất quán" sẽ làm test này đỏ.
        mockMvc.perform(post("/api/translate")
                        .header("Authorization", bearer(tokenB))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"text\":\"mitigate\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cached").value(true));
    }
}
