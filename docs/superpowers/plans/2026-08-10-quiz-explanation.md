# Giải thích đáp án quiz — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm nút "Giải thích" vào màn quiz — bấm mới gọi Gemini để nhận giải thích tiếng Việt bám theo câu trả lời của người học, nghĩa của đáp án, và bản dịch câu tiếng Anh liên quan.

**Architecture:** Một endpoint mới `POST /api/quiz/explain` nhận đúng `quizItemId`, tự đọc `quiz_attempt` gần nhất (đó là chốt chặn: chưa trả lời thì 404, vì response chứa đáp án), rồi gọi Gemini một lượt với prompt riêng theo từng `QuizType`. Không có migration Flyway, không lưu giải thích xuống DB, không tăng version prompt nào đang có nên không đề nào trong DB bị mất hiệu lực. Phía extension thêm một message type `EXPLAIN_QUIZ` đi qua service worker như mọi luồng khác.

**Tech Stack:** Spring Boot 3.4.1 / Java 21 / JPA / Testcontainers + Mockito; React 18 + TypeScript 5.7 + Vite + Vitest/RTL.

**Spec:** `docs/superpowers/specs/2026-08-10-quiz-explanation-design.md`

---

## Cấu trúc file

**Backend — tạo mới:**
- `backend/src/main/resources/prompts/quiz-explain-fill-blank.md` — prompt giải thích câu điền từ
- `backend/src/main/resources/prompts/quiz-explain-collocation.md` — prompt giải thích câu chọn cụm
- `backend/src/main/resources/prompts/quiz-explain-free-write.md` — prompt giải thích câu tự viết
- `backend/src/main/java/com/hiepnn/ieltstranslator/quiz/dto/ExplanationDto.java` — response
- `backend/src/main/java/com/hiepnn/ieltstranslator/quiz/dto/ExplainQuizRequest.java` — request
- `backend/src/test/java/com/hiepnn/ieltstranslator/quiz/QuizExplainIT.java` — IT cho endpoint

**Backend — sửa:**
- `QuizAttemptRepository.java` — thêm truy vấn lượt làm gần nhất
- `QuizService.java` — thêm `explain()` + ba hàm dựng đầu vào theo loại
- `QuizController.java` — thêm `POST /explain`
- `PromptLoaderTest.java` — phủ ba prompt mới

**Extension — sửa:**
- `shared/types.ts` — `QuizExplanation`
- `shared/messages.ts` — `ExplainQuizRequest` + union + `ResponseMap`
- `background/api-client.ts` — `explainQuiz()`
- `background/service-worker.ts` — `case 'EXPLAIN_QUIZ'`
- `sidepanel/QuizTab.tsx` — nút + ba khối hiển thị
- `sidepanel/styles.css` — `.quiz-explain`, `.quiz-explanation`, `.quiz-sentence-en`
- Ba file test cạnh chúng: `api-client.test.ts`, `service-worker.test.ts`, `QuizTab.test.tsx`

---

### Task 1: Ba file prompt giải thích

**Files:**
- Create: `backend/src/main/resources/prompts/quiz-explain-fill-blank.md`
- Create: `backend/src/main/resources/prompts/quiz-explain-collocation.md`
- Create: `backend/src/main/resources/prompts/quiz-explain-free-write.md`
- Modify: `backend/src/test/java/com/hiepnn/ieltstranslator/translation/PromptLoaderTest.java`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `PromptLoaderTest`, ngay sau method `loadsQuizPrompts()`:

```java
    @Test
    @DisplayName("Ba prompt giải thích đọc được và có đủ placeholder theo loại")
    void loadsQuizExplainPrompts() {
        for (String file : java.util.List.of("quiz-explain-fill-blank.md",
                                             "quiz-explain-collocation.md",
                                             "quiz-explain-free-write.md")) {
            PromptTemplate template = loader.load(file);
            assertThat(template.version()).as("%s phải có version dương", file).isPositive();
            assertThat(template.body()).as("%s không được rỗng", file).isNotBlank();
            // {{USER_ANSWER}} là điều kiện để giải thích BÁM THEO câu trả lời của người
            // học. Thiếu nó thì prompt lặng lẽ tụt về giải thích chung chung và không có
            // gì trong hệ thống phát hiện ra.
            assertThat(template.body()).as("%s phải có {{USER_ANSWER}}", file)
                    .contains("{{USER_ANSWER}}");
        }
        assertThat(loader.load("quiz-explain-fill-blank.md").body())
                .contains("{{SENTENCE}}", "{{ANSWER}}");
        assertThat(loader.load("quiz-explain-collocation.md").body())
                .contains("{{OPTIONS}}", "{{ANSWER}}");
        assertThat(loader.load("quiz-explain-free-write.md").body())
                .contains("{{TERM}}", "{{SENTENCE_EN}}");
    }
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=PromptLoaderTest
```

Expected: FAIL — `loadsQuizExplainPrompts` ném `UncheckedIOException: Không đọc được prompt: prompts/quiz-explain-fill-blank.md`.

- [ ] **Step 3: Tạo `quiz-explain-fill-blank.md`**

```markdown
version: 1
---
Bạn đang giải thích đáp án một câu điền từ cho người học IELTS người Việt.

Câu hỏi (dấu `___` là chỗ trống): {{SENTENCE}}
Đáp án đúng: {{ANSWER}}
Từ gốc trong sổ từ: {{TERM}} ({{POS}}) — {{MEANING_VI}}
Người học đã điền: {{USER_ANSWER}}

Trả về JSON đúng schema đã cho:

- explanation_vi: 2–4 câu TIẾNG VIỆT ĐỦ DẤU. Nói vì sao đáp án đúng hợp với chính câu này —
  dựa vào chủ ngữ, tân ngữ, collocation, dạng từ, chứ không nêu định nghĩa từ điển suông.
  Nếu "Người học đã điền" KHÁC đáp án và không rỗng, chỉ thẳng vì sao từ đó không hợp ở đây.
  Nếu phần đó RỖNG thì người học đã bỏ qua câu — đừng nhắc tới lựa chọn của họ dưới bất kỳ
  hình thức nào, chỉ giải thích đáp án.
- answer_meaning_vi: nghĩa tiếng Việt của ĐÁP ÁN trong đúng ngữ cảnh câu này, dạng ngắn
  "từ = nghĩa". Nghĩa trong sổ từ ở trên là tham khảo — đừng mâu thuẫn với nó.
- sentence_vi: bản dịch tiếng Việt tự nhiên của câu đã điền đáp án vào chỗ trống.

KHÔNG trả về `sentence_en`: câu tiếng Anh đã có sẵn, chép lại chỉ tạo cơ hội chép sai.
```

- [ ] **Step 4: Tạo `quiz-explain-collocation.md`**

```markdown
version: 1
---
Bạn đang giải thích đáp án một câu trắc nghiệm collocation cho người học IELTS người Việt.

Từ đang hỏi: {{TERM}} ({{POS}}) — {{MEANING_VI}}
Câu hỏi: {{QUESTION}}
Các lựa chọn:
{{OPTIONS}}
Cụm đúng: {{ANSWER}}
Người học đã chọn: {{USER_ANSWER}}

Trả về JSON đúng schema đã cho:

- explanation_vi: 2–4 câu TIẾNG VIỆT ĐỦ DẤU. Nói vì sao cụm đúng là cách người bản ngữ thật
  sự nói. Nếu "Người học đã chọn" là một cụm khác và không rỗng, chỉ thẳng vì sao cụm đó nghe
  không tự nhiên — sai nghĩa, sai giới từ, hay đơn giản là không ai ghép như vậy. Nếu phần đó
  RỖNG thì người học đã bỏ qua câu; đừng nhắc tới lựa chọn của họ.
- answer_meaning_vi: nghĩa tiếng Việt của CẢ CỤM đúng, dạng ngắn "cụm = nghĩa".
- sentence_en: một câu tiếng Anh học thuật 10–20 từ có dùng cụm đúng, mức IELTS band 6.5–7.
- sentence_vi: bản dịch tiếng Việt tự nhiên của CHÍNH câu `sentence_en` bạn vừa viết.
```

- [ ] **Step 5: Tạo `quiz-explain-free-write.md`**

```markdown
version: 1
---
Bạn đang giải thích cách dùng một từ cho người học IELTS người Việt, sau khi họ đã tự viết
một câu với từ đó.

Từ phải dùng: {{TERM}} ({{POS}}) — {{MEANING_VI}}
Định nghĩa tiếng Anh: {{DEFINITION_EN}}
Câu người học viết: {{USER_ANSWER}}
Câu mẫu cần dịch: {{SENTENCE_EN}}

Trả về JSON đúng schema đã cho:

- explanation_vi: 2–4 câu TIẾNG VIỆT ĐỦ DẤU về CÁCH DÙNG từ này — đi với giới từ nào, hợp
  văn cảnh nào, người học Việt hay dùng sai thế nào. Nếu "Câu người học viết" không rỗng, chỉ
  thẳng chỗ câu đó lệch so với cách dùng chuẩn; nếu RỖNG thì họ đã bỏ qua câu, chỉ dạy cách
  dùng. Đây KHÔNG phải chỗ chấm điểm lại: nhận xét bài đã hiện ở khối khác, đừng lặp lại nó.
- answer_meaning_vi: nghĩa tiếng Việt của từ phải dùng, dạng ngắn "từ = nghĩa".
- sentence_vi: bản dịch tiếng Việt tự nhiên của "Câu mẫu cần dịch". Nếu phần đó RỖNG thì trả
  về chuỗi rỗng — đừng bịa ra một câu không ai yêu cầu.

KHÔNG trả về `sentence_en`: câu tiếng Anh đã có sẵn ở trên.
```

- [ ] **Step 6: Chạy lại test**

```bash
cd backend && mvn test -Dtest=PromptLoaderTest
```

Expected: PASS (tất cả test trong class).

- [ ] **Step 7: Commit**

```bash
git add backend/src/main/resources/prompts/quiz-explain-*.md \
        backend/src/test/java/com/hiepnn/ieltstranslator/translation/PromptLoaderTest.java
git commit -m "feat(be): ba prompt giải thích đáp án quiz"
```

---

### Task 2: Endpoint `/api/quiz/explain` + nhánh FILL_BLANK

**Files:**
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/quiz/dto/ExplanationDto.java`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/quiz/dto/ExplainQuizRequest.java`
- Create: `backend/src/test/java/com/hiepnn/ieltstranslator/quiz/QuizExplainIT.java`
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/quiz/QuizAttemptRepository.java`
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/quiz/QuizService.java`
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/quiz/QuizController.java`

- [ ] **Step 1: Viết test thất bại — tạo `QuizExplainIT.java`**

```java
package com.hiepnn.ieltstranslator.quiz;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiTimeout;
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
import org.springframework.test.web.servlet.ResultActions;

import java.util.Map;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Endpoint giải thích đáp án. Gemini bị {@code @MockitoBean} chứ không phải WireMock —
 * đúng lối QuizControllerIT đang dùng; WireMock chỉ có chỗ khi thứ đang test là tầng HTTP.
 */
@AutoConfigureMockMvc
class QuizExplainIT extends AbstractPostgresIT {

    @Autowired MockMvc mockMvc;
    @Autowired VocabEntryRepository vocab;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    @MockitoBean GeminiClient geminiClient;

    @BeforeEach
    void clean() {
        reset(geminiClient);
        jdbc.update("DELETE FROM quiz_attempt");
        jdbc.update("DELETE FROM quiz_item");
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM srs_distractor");
        jdbc.update("DELETE FROM vocab_entry");
    }

    /** Một từ đã ôn ít nhất một lượt — điều kiện để lọt vào danh sách ứng viên. */
    private Long seedReviewedWord(String term, String meaningVi) {
        VocabEntry v = new VocabEntry();
        v.setTerm(term);
        v.setLemma(term);
        v.setLang("en");
        v.setPos("verb");
        v.setMeaningVi(meaningVi);
        v.setCollocations(objectMapper.createArrayNode());
        v.setExamples(objectMapper.createArrayNode());
        Long id = vocab.saveAndFlush(v).getId();
        jdbc.update("""
                INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses)
                VALUES (?, CURRENT_DATE, 'REVIEW', 3, 1)""", id);
        return id;
    }

    private long generateOne(String type) throws Exception {
        String body = mockMvc.perform(post("/api/quiz/generate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"count\":5,\"type\":\"%s\"}".formatted(type)))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(body).get(0).get("id").asLong();
    }

    private void answer(long quizItemId, String answer) throws Exception {
        mockMvc.perform(post("/api/quiz/answer")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                Map.of("quizItemId", quizItemId, "answer", answer))))
                .andExpect(status().isOk());
    }

    private ResultActions explain(long quizItemId) throws Exception {
        return mockMvc.perform(post("/api/quiz/explain")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"quizItemId\":%d}".formatted(quizItemId)));
    }

    /**
     * Đặt lại stub Gemini SAU khi đã nộp bài. Cần thiết vì chấm FREE_WRITE và giải thích
     * dùng chung GeminiTimeout.QUIZ_GRADE, nên không phân biệt được hai lượt bằng matcher.
     */
    private void stubExplain(String json) throws Exception {
        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE)))
                .thenReturn(objectMapper.readTree(json));
    }

    private void stubFillBlankGenerate(String sentence, String answer) throws Exception {
        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE)))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"mitigate","sentence":"%s","answer":"%s",
                  "hint":"làm nhẹ bớt"}]}""".formatted(sentence, answer)));
    }

    @Test
    @DisplayName("FILL_BLANK: sentenceEn là câu đề bài ĐÃ điền đáp án, ghép ở backend")
    void fillBlankSentenceIsFilledByBackend() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubFillBlankGenerate("Governments must ___ the impact of flooding.", "mitigate");
        long id = generateOne("FILL_BLANK");
        answer(id, "reduce");

        // Gemini CỐ Ý trả sentence_en rác: với loại này backend đã biết câu tiếng Anh nên
        // phải bỏ qua hoàn toàn chuỗi Gemini trả về.
        stubExplain("""
                {"explanation_vi":"\\"mitigate\\" đi với impact; \\"reduce\\" nhạt hơn.",
                 "answer_meaning_vi":"mitigate = giảm nhẹ",
                 "sentence_en":"CÂU RÁC GEMINI TỰ BỊA",
                 "sentence_vi":"Chính phủ phải giảm nhẹ tác động của lũ lụt."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn")
                        .value("Governments must mitigate the impact of flooding."))
                .andExpect(jsonPath("$.sentenceVi")
                        .value("Chính phủ phải giảm nhẹ tác động của lũ lụt."))
                .andExpect(jsonPath("$.answerMeaning").value("mitigate = giảm nhẹ"))
                .andExpect(jsonPath("$.explanation").value(containsString("reduce")));
    }

    @Test
    @DisplayName("FILL_BLANK bỏ qua câu vẫn giải thích được và vẫn đủ cặp câu")
    void skippedFillBlankStillExplained() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubFillBlankGenerate("Governments must ___ the impact of flooding.", "mitigate");
        long id = generateOne("FILL_BLANK");
        answer(id, "");

        stubExplain("""
                {"explanation_vi":"\\"mitigate\\" là làm nhẹ tác động tiêu cực.",
                 "answer_meaning_vi":"mitigate = giảm nhẹ",
                 "sentence_vi":"Chính phủ phải giảm nhẹ tác động của lũ lụt."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn")
                        .value("Governments must mitigate the impact of flooding."))
                .andExpect(jsonPath("$.sentenceVi")
                        .value("Chính phủ phải giảm nhẹ tác động của lũ lụt."));
    }
}
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=QuizExplainIT
```

Expected: FAIL — cả hai test trả 404 vì `/api/quiz/explain` chưa tồn tại (`status().isOk()` không khớp).

- [ ] **Step 3: Tạo `ExplanationDto.java`**

```java
package com.hiepnn.ieltstranslator.quiz.dto;

/**
 * Giải thích một câu ĐÃ trả lời. KHÔNG lưu xuống DB — sinh lúc người học bấm nút và chỉ
 * sống trong đúng một response.
 *
 * @param explanation   LUÔN non-null và khác rỗng, tiếng Việt. Bám theo câu trả lời của
 *                      người học khi họ có trả lời; chỉ giải thích đáp án khi họ bỏ qua.
 * @param answerMeaning LUÔN non-null và khác rỗng. Nghĩa tiếng Việt của từ/cụm đáp án
 *                      trong đúng ngữ cảnh câu.
 * @param sentenceEn    Câu tiếng Anh đi kèm bản dịch. CẶP ĐÔI với {@code sentenceVi}: cùng
 *                      null hoặc cùng non-null, không bao giờ một nửa. Cùng null xảy ra
 *                      đúng một ca — FREE_WRITE bị bỏ qua nên không có câu nào để dịch.
 * @param sentenceVi    Bản dịch tiếng Việt của {@code sentenceEn}.
 */
public record ExplanationDto(String explanation,
                             String answerMeaning,
                             String sentenceEn,
                             String sentenceVi) {
}
```

- [ ] **Step 4: Tạo `ExplainQuizRequest.java`**

```java
package com.hiepnn.ieltstranslator.quiz.dto;

import jakarta.validation.constraints.NotNull;

/**
 * CỐ Ý chỉ mang {@code quizItemId} và không nhận câu trả lời từ client.
 *
 * <p>Response của endpoint này TIẾT LỘ ĐÁP ÁN, nên nó phải tự đọc {@code quiz_attempt} gần
 * nhất và từ chối khi chưa có lượt làm nào. Nhận câu trả lời do client gửi lên rồi tin luôn
 * là biến {@code /explain} thành đường vòng đọc đáp án trước khi trả lời — đúng thứ mà
 * QuizItemDto cố ý bảo vệ.
 */
public record ExplainQuizRequest(
        @NotNull(message = "không được bỏ trống") Long quizItemId) {
}
```

- [ ] **Step 5: Thêm truy vấn vào `QuizAttemptRepository.java`**

Thay toàn bộ nội dung file:

```java
package com.hiepnn.ieltstranslator.quiz;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface QuizAttemptRepository extends JpaRepository<QuizAttempt, Long> {

    /**
     * Lượt làm gần nhất của một item.
     *
     * <p>Sắp theo {@code id} giảm dần chứ KHÔNG theo {@code created_at}: cột đó mặc định
     * {@code now()}, mà {@code now()} trong Postgres là thời điểm bắt đầu transaction — hai
     * lượt trong cùng một transaction sẽ trùng mốc thời gian và thứ tự thành ngẫu nhiên.
     * {@code id} là BIGSERIAL nên luôn tăng.
     */
    Optional<QuizAttempt> findFirstByQuizItem_IdOrderByIdDesc(Long quizItemId);
}
```

- [ ] **Step 6: Thêm `explain()` vào `QuizService.java`**

Thêm import ở đầu file (cạnh các import `dto` sẵn có):

```java
import com.hiepnn.ieltstranslator.quiz.dto.ExplanationDto;
```

Thêm hằng ngay dưới `GRADE_SCHEMA`:

```java
    static final String EXPLAIN_FILL_BLANK_PROMPT = "quiz-explain-fill-blank.md";
    static final String EXPLAIN_COLLOCATION_PROMPT = "quiz-explain-collocation.md";
    static final String EXPLAIN_FREE_WRITE_PROMPT = "quiz-explain-free-write.md";

    /**
     * CHỈ hai field bắt buộc, và đó là chủ ý.
     *
     * <p>{@code sentence_en} không bắt buộc vì hai trong ba loại backend đã tự biết câu
     * tiếng Anh — nhờ Gemini chép lại một chuỗi đang cầm trong tay là mời nó chép sai.
     * {@code sentence_vi} không bắt buộc vì có đúng một ca không tồn tại câu nào để dịch
     * (FREE_WRITE bị bỏ qua); bắt buộc field đó là ép Gemini bịa ra một câu tiếng Việt
     * không gắn với câu tiếng Anh nào.
     */
    private static final Map<String, Object> EXPLAIN_SCHEMA = Map.of(
            "type", "object",
            "properties", Map.of(
                    "explanation_vi", Map.of("type", "string"),
                    "answer_meaning_vi", Map.of("type", "string"),
                    "sentence_en", Map.of("type", "string"),
                    "sentence_vi", Map.of("type", "string")),
            "required", List.of("explanation_vi", "answer_meaning_vi"));
```

Thêm method `explain()` ngay sau `answer()`:

```java
    /**
     * Giải thích một câu ĐÃ trả lời. Không ghi gì xuống DB.
     *
     * <p>Chưa có lượt làm nào thì ném NOT_FOUND TRƯỚC khi gọi Gemini: response này chứa đáp
     * án nên nó không được phục vụ một request chưa trả lời, và cũng không được đốt quota
     * cho request đó.
     */
    @Transactional(readOnly = true)
    public ExplanationDto explain(Long quizItemId) {
        QuizItem item = items.findById(quizItemId)
                .orElseThrow(() -> AppException.of(ErrorCode.NOT_FOUND,
                        "Không tìm thấy câu hỏi id=" + quizItemId));
        QuizAttempt attempt = attempts.findFirstByQuizItem_IdOrderByIdDesc(quizItemId)
                .orElseThrow(() -> AppException.of(ErrorCode.NOT_FOUND,
                        "Chưa trả lời câu này nên chưa có gì để giải thích"));

        // switch KHÔNG có nhánh default: thêm QuizType mới phải fail compile ở đây, đúng
        // nguyên tắc của toDto() và GlobalExceptionHandler.statusFor().
        ExplainInput input = switch (item.getType()) {
            case FILL_BLANK -> fillBlankInput(item, attempt);
            case COLLOCATION_CHOICE -> throw AppException.of(ErrorCode.INTERNAL,
                    "Chưa hỗ trợ giải thích loại này");
            case FREE_WRITE -> throw AppException.of(ErrorCode.INTERNAL,
                    "Chưa hỗ trợ giải thích loại này");
        };

        PromptTemplate template = prompts.load(input.promptFile());
        JsonNode payload = gemini.generateJson(template.render(input.vars()),
                EXPLAIN_SCHEMA, GeminiTimeout.QUIZ_GRADE);

        String explanation = firstNonBlank(payload.path("explanation_vi").asText(""),
                "Chưa lấy được giải thích cho câu này.");
        String answerMeaning = firstNonBlank(payload.path("answer_meaning_vi").asText(""),
                meaningFromVocab(item), "(chưa có nghĩa)");

        // knownSentenceEn khác rỗng nghĩa là BACKEND biết câu tiếng Anh; lúc đó chuỗi Gemini
        // trả về bị bỏ qua hoàn toàn.
        String sentenceEn = input.knownSentenceEn().isBlank()
                ? payload.path("sentence_en").asText("")
                : input.knownSentenceEn();
        String sentenceVi = payload.path("sentence_vi").asText("");
        // Thiếu một nửa thì bỏ cả cặp. Trả một nửa là bắt panel render khối "Dịch câu" với
        // đúng một dòng trống.
        if (sentenceEn.isBlank() || sentenceVi.isBlank()) {
            sentenceEn = null;
            sentenceVi = null;
        }
        return new ExplanationDto(explanation, answerMeaning, sentenceEn, sentenceVi);
    }

    /**
     * Đầu vào đã chuẩn hoá cho một lượt giải thích.
     *
     * @param knownSentenceEn câu tiếng Anh backend đã biết. RỖNG nghĩa là backend không có
     *                        câu nào — hoặc vì loại đó cần Gemini nghĩ ra
     *                        (COLLOCATION_CHOICE), hoặc vì thật sự không có câu nào tồn tại
     *                        (FREE_WRITE bị bỏ qua). Cả hai ca đều xử lý giống nhau: lấy
     *                        {@code sentence_en} Gemini trả, rỗng thì bỏ cả cặp.
     */
    private record ExplainInput(String promptFile, Map<String, String> vars,
                                String knownSentenceEn) {
    }

    private ExplainInput fillBlankInput(QuizItem item, QuizAttempt attempt) {
        Map<String, Object> p = item.getPayload();
        VocabEntry v = item.getVocabEntry();
        String sentence = asString(p.get("sentence"));
        String answer = asString(p.get("answer"));
        // Câu đã điền đáp án ghép ở đây chứ không nhờ Gemini. Prompt sinh đề đã bảo đảm
        // "___" xuất hiện đúng một lần trong câu.
        String filled = sentence.replace("___", answer);
        return new ExplainInput(EXPLAIN_FILL_BLANK_PROMPT, Map.of(
                "SENTENCE", sentence,
                "ANSWER", answer,
                "TERM", nullToEmpty(v.getTerm()),
                "POS", nullToEmpty(v.getPos()),
                "MEANING_VI", nullToEmpty(v.getMeaningVi()),
                "USER_ANSWER", nullToEmpty(attempt.getUserAnswer())),
                filled);
    }

    /** Nghĩa lấy từ chính sổ từ của người dùng, làm lưới hứng khi Gemini trả rỗng. */
    private String meaningFromVocab(QuizItem item) {
        VocabEntry v = item.getVocabEntry();
        return (v.getMeaningVi() == null || v.getMeaningVi().isBlank())
                ? "" : v.getTerm() + " = " + v.getMeaningVi();
    }

    /** Giá trị đầu tiên khác rỗng; hết sạch thì trả chuỗi rỗng. */
    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return "";
    }
```

- [ ] **Step 7: Thêm endpoint vào `QuizController.java`**

Thêm import:

```java
import com.hiepnn.ieltstranslator.quiz.dto.ExplainQuizRequest;
import com.hiepnn.ieltstranslator.quiz.dto.ExplanationDto;
```

Thêm method sau `answer()`:

```java
    /**
     * Giải thích một câu ĐÃ trả lời. Response chứa đáp án, nên endpoint chỉ phục vụ item đã
     * có lượt làm — chốt chặn đó nằm trong QuizService.explain().
     */
    @PostMapping("/explain")
    public ExplanationDto explain(@Valid @RequestBody ExplainQuizRequest request) {
        return quizService.explain(request.quizItemId());
    }
```

- [ ] **Step 8: Chạy test để xác nhận nó xanh**

```bash
cd backend && mvn test -Dtest=QuizExplainIT
```

Expected: PASS — 2 test.

- [ ] **Step 9: Commit**

```bash
git add backend/src/main/java/com/hiepnn/ieltstranslator/quiz/ \
        backend/src/test/java/com/hiepnn/ieltstranslator/quiz/QuizExplainIT.java
git commit -m "feat(be): endpoint /api/quiz/explain và nhánh FILL_BLANK"
```

---

### Task 3: Nhánh COLLOCATION_CHOICE

**Files:**
- Modify: `backend/src/test/java/com/hiepnn/ieltstranslator/quiz/QuizExplainIT.java`
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/quiz/QuizService.java`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `QuizExplainIT` một helper và hai test:

```java
    private void stubCollocationGenerate() throws Exception {
        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GENERATE)))
                .thenReturn(objectMapper.readTree("""
                {"items":[{"term":"mitigate",
                  "question":"Cụm nào đi với «mitigate» là tự nhiên?",
                  "options":["mitigate the risk","mitigate a cake","mitigate loudly",
                             "mitigate blue"],
                  "correct_index":0}]}"""));
    }

    /** Vị trí 0-based của một cụm trong options ĐÃ XÁO của item đang lưu. */
    private int indexOfOption(long quizItemId, String option) {
        String options = jdbc.queryForObject(
                "SELECT payload->>'options' FROM quiz_item WHERE id = ?", String.class,
                quizItemId);
        try {
            var array = objectMapper.readTree(options);
            for (int i = 0; i < array.size(); i++) {
                if (option.equals(array.get(i).asText())) {
                    return i;
                }
            }
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
        throw new IllegalStateException("Không tìm thấy lựa chọn: " + option);
    }

    @Test
    @DisplayName("COLLOCATION_CHOICE: sentenceEn lấy từ Gemini vì backend không có câu nào")
    void collocationSentenceComesFromGemini() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocationGenerate();
        long id = generateOne("COLLOCATION_CHOICE");
        answer(id, String.valueOf(indexOfOption(id, "mitigate a cake")));

        stubExplain("""
                {"explanation_vi":"«mitigate the risk» là cách người bản ngữ nói.",
                 "answer_meaning_vi":"mitigate the risk = giảm thiểu rủi ro",
                 "sentence_en":"Careful planning can mitigate the risk of flooding.",
                 "sentence_vi":"Quy hoạch cẩn thận có thể giảm thiểu rủi ro lũ lụt."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn")
                        .value("Careful planning can mitigate the risk of flooding."))
                .andExpect(jsonPath("$.sentenceVi")
                        .value("Quy hoạch cẩn thận có thể giảm thiểu rủi ro lũ lụt."))
                .andExpect(jsonPath("$.answerMeaning")
                        .value("mitigate the risk = giảm thiểu rủi ro"));
    }

    @Test
    @DisplayName("Prompt nhận NỘI DUNG cụm người học chọn, không phải index dạng chuỗi")
    void collocationPromptCarriesChosenOptionText() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocationGenerate();
        long id = generateOne("COLLOCATION_CHOICE");
        answer(id, String.valueOf(indexOfOption(id, "mitigate a cake")));

        stubExplain("""
                {"explanation_vi":"x","answer_meaning_vi":"y",
                 "sentence_en":"z","sentence_vi":"t"}""");
        explain(id).andExpect(status().isOk());

        // Đưa "2" vào prompt thì Gemini không có cách nào biết người học đã chọn gì, và
        // "chỉ thẳng chỗ sai" tụt về giải thích chung chung mà không ai phát hiện.
        ArgumentCaptor<String> prompt = ArgumentCaptor.forClass(String.class);
        verify(geminiClient).generateJson(prompt.capture(), any(),
                                          eq(GeminiTimeout.QUIZ_GRADE));
        assertThat(prompt.getValue()).contains("mitigate a cake");
        assertThat(prompt.getValue()).contains("mitigate the risk");
    }

    @Test
    @DisplayName("Bỏ qua câu chọn cụm: prompt nhận USER_ANSWER RỖNG, không phải cụm số 0")
    void skippedCollocationSendsEmptyUserAnswer() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocationGenerate();
        long id = generateOne("COLLOCATION_CHOICE");
        answer(id, "");

        stubExplain("""
                {"explanation_vi":"x","answer_meaning_vi":"y",
                 "sentence_en":"z","sentence_vi":"t"}""");
        explain(id).andExpect(status().isOk());

        // Chuỗi rỗng KHÔNG được hiểu thành index 0. Nếu optionAt trả về options.get(0)
        // thì prompt sẽ nói "bạn đã chọn «mitigate the risk»" với người vừa bỏ qua câu —
        // vừa sai sự thật, vừa đúng bằng đáp án.
        ArgumentCaptor<String> prompt = ArgumentCaptor.forClass(String.class);
        verify(geminiClient).generateJson(prompt.capture(), any(),
                                          eq(GeminiTimeout.QUIZ_GRADE));
        // Regex chứ không so chuỗi thẳng: dòng đó là "Người học đã chọn: {{USER_ANSWER}}",
        // có một dấu cách trước placeholder. Bất biến cần khẳng định là "không còn gì
        // ngoài khoảng trắng trên dòng đó", chứ không phải số dấu cách.
        assertThat(prompt.getValue()).containsPattern("Người học đã chọn:\\s*\\n");
    }
```

Thêm import còn thiếu vào đầu file:

```java
import org.mockito.ArgumentCaptor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=QuizExplainIT
```

Expected: FAIL — hai test mới trả 500 với message "Chưa hỗ trợ giải thích loại này".

- [ ] **Step 3: Thay nhánh tạm bằng cài đặt thật**

Trong `QuizService.explain()`, đổi dòng:

```java
            case COLLOCATION_CHOICE -> throw AppException.of(ErrorCode.INTERNAL,
                    "Chưa hỗ trợ giải thích loại này");
```

thành:

```java
            case COLLOCATION_CHOICE -> collocationInput(item, attempt);
```

Thêm hai method sau `fillBlankInput`:

```java
    private ExplainInput collocationInput(QuizItem item, QuizAttempt attempt) {
        Map<String, Object> p = item.getPayload();
        VocabEntry v = item.getVocabEntry();
        List<String> options = asStringList(p.get("options"));
        int correctIndex = asInt(p.get("correct_index"));
        String correctOption = (correctIndex >= 0 && correctIndex < options.size())
                ? options.get(correctIndex) : "";

        StringBuilder rendered = new StringBuilder();
        for (int i = 0; i < options.size(); i++) {
            rendered.append(i + 1).append(". ").append(options.get(i)).append('\n');
        }

        return new ExplainInput(EXPLAIN_COLLOCATION_PROMPT, Map.of(
                "TERM", nullToEmpty(v.getTerm()),
                "POS", nullToEmpty(v.getPos()),
                "MEANING_VI", nullToEmpty(v.getMeaningVi()),
                "QUESTION", asString(p.get("question")),
                "OPTIONS", rendered.toString().strip(),
                "ANSWER", correctOption,
                // Câu trả lời lưu trong attempt là INDEX dạng chuỗi. Dịch ngược ra nội
                // dung cụm ngay tại đây: đưa "2" vào prompt thì Gemini không biết người
                // học đã chọn gì.
                "USER_ANSWER", optionAt(options, nullToEmpty(attempt.getUserAnswer()))),
                "");
    }

    /** Chuỗi không parse được thành index hợp lệ — kể cả rỗng, tức bỏ qua — trả chuỗi rỗng. */
    private String optionAt(List<String> options, String rawIndex) {
        try {
            int index = Integer.parseInt(rawIndex.strip());
            return (index >= 0 && index < options.size()) ? options.get(index) : "";
        } catch (NumberFormatException e) {
            return "";
        }
    }
```

- [ ] **Step 4: Chạy test để xác nhận nó xanh**

```bash
cd backend && mvn test -Dtest=QuizExplainIT
```

Expected: PASS — 4 test.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/hiepnn/ieltstranslator/quiz/QuizService.java \
        backend/src/test/java/com/hiepnn/ieltstranslator/quiz/QuizExplainIT.java
git commit -m "feat(be): giải thích cho câu chọn cụm từ"
```

---

### Task 4: Nhánh FREE_WRITE

**Files:**
- Modify: `backend/src/test/java/com/hiepnn/ieltstranslator/quiz/QuizExplainIT.java`
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/quiz/QuizService.java`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `QuizExplainIT`:

```java
    @Test
    @DisplayName("FREE_WRITE: sentenceEn là improvedVersion của lượt làm")
    void freeWriteSentenceIsImprovedVersion() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        long id = generateOne("FREE_WRITE");   // FREE_WRITE dựng thẳng, không gọi Gemini

        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE)))
                .thenReturn(objectMapper.readTree("""
                {"meaning_ok":true,"grammar_ok":true,"band_ok":true,"score":88,
                 "feedback_vi":"Câu dùng từ đúng nghĩa.",
                 "improved_version":"Governments must mitigate the impact of flooding."}"""));
        answer(id, "We mitigate it.");

        stubExplain("""
                {"explanation_vi":"\\"mitigate\\" đi với danh từ chỉ tác động tiêu cực.",
                 "answer_meaning_vi":"mitigate = giảm nhẹ",
                 "sentence_vi":"Chính phủ phải giảm nhẹ tác động của lũ lụt."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn")
                        .value("Governments must mitigate the impact of flooding."))
                .andExpect(jsonPath("$.sentenceVi")
                        .value("Chính phủ phải giảm nhẹ tác động của lũ lụt."));
    }

    @Test
    @DisplayName("FREE_WRITE không có improvedVersion thì sentenceEn là chính câu người học")
    void freeWriteFallsBackToUserSentence() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        long id = generateOne("FREE_WRITE");

        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE)))
                .thenReturn(objectMapper.readTree("""
                {"meaning_ok":true,"grammar_ok":true,"band_ok":true,"score":92,
                 "feedback_vi":"Câu đã tốt."}"""));
        answer(id, "We must mitigate the damage.");

        stubExplain("""
                {"explanation_vi":"Dùng đúng rồi.","answer_meaning_vi":"mitigate = giảm nhẹ",
                 "sentence_vi":"Chúng ta phải giảm nhẹ thiệt hại."}""");

        explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.sentenceEn").value("We must mitigate the damage."))
                .andExpect(jsonPath("$.sentenceVi").value("Chúng ta phải giảm nhẹ thiệt hại."));
    }

    @Test
    @DisplayName("FREE_WRITE bỏ qua câu: sentenceEn và sentenceVi CÙNG null")
    void skippedFreeWriteHasNoSentencePair() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        long id = generateOne("FREE_WRITE");
        answer(id, "");   // bỏ qua: QuizService không gọi Gemini để chấm

        stubExplain("""
                {"explanation_vi":"\\"mitigate\\" dùng với tác động tiêu cực.",
                 "answer_meaning_vi":"mitigate = giảm nhẹ","sentence_vi":""}""");

        String body = explain(id)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.explanation").value(containsString("mitigate")))
                .andReturn().getResponse().getContentAsString();

        // Khoá PHẢI có mặt với giá trị null: mirror TypeScript khai `string | null` chứ
        // không phải optional, hai bên chỉ khớp khi khoá luôn xuất hiện.
        var node = objectMapper.readTree(body);
        assertThat(node.has("sentenceEn")).isTrue();
        assertThat(node.get("sentenceEn").isNull()).isTrue();
        assertThat(node.get("sentenceVi").isNull()).isTrue();
    }
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=QuizExplainIT
```

Expected: FAIL — ba test mới trả 500 với message "Chưa hỗ trợ giải thích loại này".

- [ ] **Step 3: Thay nhánh tạm bằng cài đặt thật**

Trong `QuizService.explain()`, đổi:

```java
            case FREE_WRITE -> throw AppException.of(ErrorCode.INTERNAL,
                    "Chưa hỗ trợ giải thích loại này");
```

thành:

```java
            case FREE_WRITE -> freeWriteInput(item, attempt);
```

Thêm method sau `optionAt`:

```java
    private ExplainInput freeWriteInput(QuizItem item, QuizAttempt attempt) {
        VocabEntry v = item.getVocabEntry();
        String userAnswer = nullToEmpty(attempt.getUserAnswer());
        // Câu viết lại là câu mẫu đáng học nhất; không có thì lấy chính câu người học.
        // Bỏ qua câu thì cả hai đều rỗng — lúc đó KHÔNG có câu nào để dịch, và cặp
        // sentenceEn/sentenceVi sẽ cùng về null ở chỗ ghép kết quả.
        String sentenceEn = firstNonBlank(nullToEmpty(attempt.getImprovedVersion()), userAnswer);
        return new ExplainInput(EXPLAIN_FREE_WRITE_PROMPT, Map.of(
                "TERM", nullToEmpty(v.getTerm()),
                "POS", nullToEmpty(v.getPos()),
                "MEANING_VI", nullToEmpty(v.getMeaningVi()),
                "DEFINITION_EN", nullToEmpty(v.getDefinitionEn()),
                "USER_ANSWER", userAnswer,
                "SENTENCE_EN", sentenceEn),
                sentenceEn);
    }
```

- [ ] **Step 4: Chạy test để xác nhận nó xanh**

```bash
cd backend && mvn test -Dtest=QuizExplainIT
```

Expected: PASS — 7 test.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/hiepnn/ieltstranslator/quiz/QuizService.java \
        backend/src/test/java/com/hiepnn/ieltstranslator/quiz/QuizExplainIT.java
git commit -m "feat(be): giải thích cho câu tự viết"
```

---

### Task 5: Các chốt chặn — chưa trả lời, id lạ, Gemini chết, nửa cặp câu

**Files:**
- Modify: `backend/src/test/java/com/hiepnn/ieltstranslator/quiz/QuizExplainIT.java`

Không có code sản phẩm mới ở task này: các nhánh đã viết ở Task 2. Đây là bốn khẳng định
riêng cho những hành vi dễ vỡ im lặng nhất.

- [ ] **Step 1: Viết test**

Thêm vào `QuizExplainIT`:

```java
    @Test
    @DisplayName("Chưa trả lời thì 404 và KHÔNG gọi Gemini — không đọc trộm được đáp án")
    void explainBeforeAnsweringIsRejectedWithoutBurningQuota() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubFillBlankGenerate("Governments must ___ the impact.", "mitigate");
        long id = generateOne("FILL_BLANK");

        explain(id)
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"))
                .andExpect(jsonPath("$.retryable").value(false));

        // Không một call QUIZ_GRADE nào: vừa là chuyện quota, vừa là bằng chứng chốt chặn
        // nằm TRƯỚC lượt gọi Gemini chứ không phải sau.
        verify(geminiClient, never()).generateJson(anyString(), any(),
                                                   eq(GeminiTimeout.QUIZ_GRADE));
    }

    @Test
    @DisplayName("quizItemId không tồn tại → 404 NOT_FOUND")
    void unknownItemIsNotFound() throws Exception {
        explain(999999)
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"))
                .andExpect(jsonPath("$.retryable").value(false));
    }

    @Test
    @DisplayName("Gemini chết → GEMINI_UNAVAILABLE truyền nguyên, retry được")
    void geminiFailurePropagates() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubFillBlankGenerate("Governments must ___ the impact.", "mitigate");
        long id = generateOne("FILL_BLANK");
        answer(id, "reduce");

        when(geminiClient.generateJson(anyString(), any(), eq(GeminiTimeout.QUIZ_GRADE)))
                .thenThrow(AppException.of(ErrorCode.GEMINI_UNAVAILABLE,
                        "Gemini đang không phản hồi"));

        explain(id)
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value("GEMINI_UNAVAILABLE"))
                .andExpect(jsonPath("$.retryable").value(true));
    }

    @Test
    @DisplayName("Gemini trả sentence_vi rỗng → bỏ CẢ CẶP, không trả một nửa")
    void halfSentencePairIsDroppedEntirely() throws Exception {
        seedReviewedWord("mitigate", "giảm nhẹ");
        stubCollocationGenerate();
        long id = generateOne("COLLOCATION_CHOICE");
        answer(id, String.valueOf(indexOfOption(id, "mitigate the risk")));

        stubExplain("""
                {"explanation_vi":"Cụm này tự nhiên.","answer_meaning_vi":"= giảm rủi ro",
                 "sentence_en":"Careful planning can mitigate the risk.","sentence_vi":""}""");

        String body = explain(id)
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        // sentenceEn có giá trị thật nhưng thiếu bản dịch: giữ lại nó là bắt panel render
        // khối "Dịch câu" với đúng một dòng tiếng Anh và không có dịch.
        var node = objectMapper.readTree(body);
        assertThat(node.get("sentenceEn").isNull()).isTrue();
        assertThat(node.get("sentenceVi").isNull()).isTrue();
    }
```

Thêm import còn thiếu:

```java
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;

import static org.mockito.Mockito.never;
```

- [ ] **Step 2: Chạy toàn bộ test backend**

```bash
cd backend && mvn test
```

Expected: PASS — toàn bộ, gồm 11 test trong `QuizExplainIT`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/test/java/com/hiepnn/ieltstranslator/quiz/QuizExplainIT.java
git commit -m "test(be): chốt chặn cho endpoint giải thích đáp án"
```

---

### Task 6: Hợp đồng phía extension

**Files:**
- Modify: `extension/src/shared/types.ts`
- Modify: `extension/src/shared/messages.ts`

- [ ] **Step 1: Thêm `QuizExplanation` vào `types.ts`**

Thêm ngay sau `interface AnswerResult`:

```ts
/**
 * Gương của ExplanationDto phía backend.
 *
 * KHÔNG nằm trong QuizItemDto và cũng không nằm trong AnswerResult: nó chứa đáp án nên chỉ
 * lấy được qua EXPLAIN_QUIZ, sau khi câu đã có lượt làm.
 *
 * `sentenceEn` và `sentenceVi` là MỘT CẶP — cùng null hoặc cùng non-null, backend không bao
 * giờ gửi một nửa. Cùng null xảy ra đúng một ca: FREE_WRITE bị bỏ qua nên không có câu nào
 * để dịch.
 */
export interface QuizExplanation {
  explanation: string;
  answerMeaning: string;
  sentenceEn: string | null;
  sentenceVi: string | null;
}
```

- [ ] **Step 2: Thêm message type vào `messages.ts`**

Thêm `QuizExplanation` vào danh sách import từ `./types`:

```ts
import type {
  AnswerResult, ApiError, CardDto, PageResponse, QuizExplanation, QuizItemDto, QuizType,
  Rating, ReviewResponse, SaveVocabResponse, SrsStats, TranslateResult, VocabEntryDto,
} from './types';
```

Thêm interface ngay sau `AnswerQuizRequest`:

```ts
/**
 * CỐ Ý không mang câu trả lời, dù panel đang giữ nó: backend tự đọc lượt làm gần nhất và
 * trả 404 khi chưa có. Response chứa đáp án, nên gửi kèm câu trả lời từ đây là mở một đường
 * vòng đọc đáp án trước khi trả lời.
 */
export interface ExplainQuizRequest {
  type: 'EXPLAIN_QUIZ';
  quizItemId: number;
}
```

Thêm vào union `ExtensionRequest`, sau `AnswerQuizRequest`:

```ts
  | AnswerQuizRequest
  | ExplainQuizRequest;
```

Thêm vào `ResponseMap`, sau `ANSWER_QUIZ`:

```ts
  EXPLAIN_QUIZ: QuizExplanation;
```

- [ ] **Step 3: Kiểm tra type check**

```bash
cd extension && npm run build
```

Expected: PASS. (`ResponseMap` phủ đủ union nên thiếu một khoá là fail compile ngay ở bước này.)

- [ ] **Step 4: Commit**

```bash
git add extension/src/shared/types.ts extension/src/shared/messages.ts
git commit -m "feat(ext): hợp đồng message EXPLAIN_QUIZ"
```

---

### Task 7: `ApiClient.explainQuiz`

**Files:**
- Modify: `extension/src/background/api-client.ts`
- Test: `extension/src/background/api-client.test.ts`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `api-client.test.ts`, ngay sau test `answerQuiz POST /api/quiz/answer đúng body`:

```ts
    it('explainQuiz POST /api/quiz/explain và KHÔNG gửi kèm câu trả lời', async () => {
      fetchMock.mockResolvedValue(jsonResponse({
        explanation: '"mitigate" đi với "impact".',
        answerMeaning: 'mitigate = giảm nhẹ',
        sentenceEn: 'Governments must mitigate the impact.',
        sentenceVi: 'Chính phủ phải giảm nhẹ tác động.',
      }));

      const result = await client.explainQuiz({ quizItemId: 7 });

      // Body đúng bằng { quizItemId }: thêm câu trả lời vào đây là mở đường vòng đọc đáp án.
      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE_URL}/api/quiz/explain`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ quizItemId: 7 }),
        }),
      );
      expect(result.sentenceVi).toBe('Chính phủ phải giảm nhẹ tác động.');
    });

    it('explainQuiz dùng mức chờ 50 giây như chấm bài — cũng một lượt gọi Gemini', async () => {
      const timeout = spyTimeout();
      fetchMock.mockResolvedValue(jsonResponse({
        explanation: 'x', answerMeaning: 'y', sentenceEn: null, sentenceVi: null,
      }));

      await client.explainQuiz({ quizItemId: 7 });

      expect(timeout).toHaveBeenCalledWith(50_000);
    });
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd extension && npm test -- src/background/api-client.test.ts
```

Expected: FAIL — `client.explainQuiz is not a function`.

- [ ] **Step 3: Thêm method vào `api-client.ts`**

Thêm `QuizExplanation` vào danh sách import từ `../shared/types` (dòng 2), rồi thêm method
ngay sau `answerQuiz`:

```ts
  /**
   * Giải thích một câu ĐÃ trả lời. Cũng là một lượt gọi Gemini nên dùng chung mức chờ với
   * chấm bài — 40 giây mặc định là ngắn khi backend đang đợi Gemini.
   */
  async explainQuiz(args: { quizItemId: number }): Promise<QuizExplanation> {
    return this.request('/api/quiz/explain',
      { method: 'POST', body: JSON.stringify(args) }, QUIZ_ANSWER_TIMEOUT_MS);
  }
```

- [ ] **Step 4: Chạy test để xác nhận nó xanh**

```bash
cd extension && npm test -- src/background/api-client.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add extension/src/background/api-client.ts extension/src/background/api-client.test.ts
git commit -m "feat(ext): ApiClient.explainQuiz"
```

---

### Task 8: Định tuyến trong service worker

**Files:**
- Modify: `extension/src/background/service-worker.ts`
- Test: `extension/src/background/service-worker.test.ts`

- [ ] **Step 1: Viết test thất bại**

Trong `service-worker.test.ts`, thêm `explainQuiz: vi.fn(),` vào object `api` (ngay sau
`answerQuiz: vi.fn(),`). Rồi thêm test sau test `ANSWER_QUIZ xuống answerQuiz…`:

```ts
    it('EXPLAIN_QUIZ xuống explainQuiz kèm ĐÚNG quizItemId và không gì khác', async () => {
      api.explainQuiz.mockResolvedValue({
        explanation: 'x', answerMeaning: 'y', sentenceEn: null, sentenceVi: null,
      });
      await loadServiceWorker();

      const response = await send({ type: 'EXPLAIN_QUIZ', quizItemId: 12 });

      expect(api.explainQuiz).toHaveBeenCalledWith({ quizItemId: 12 });
      expect(response).toMatchObject({ ok: true, data: { explanation: 'x' } });
    });
```

Và trong `describe('các điểm làm badge đổi số', …)`, sau test `nộp bài quiz KHÔNG đụng tới
badge`:

```ts
    it('xin giải thích KHÔNG đụng tới badge — quiz không chạm lịch SRS', async () => {
      api.explainQuiz.mockResolvedValue({
        explanation: 'x', answerMeaning: 'y', sentenceEn: null, sentenceVi: null,
      });
      await loadServiceWorker();

      await send({ type: 'EXPLAIN_QUIZ', quizItemId: 12 });

      expect(refreshBadge).not.toHaveBeenCalled();
    });
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd extension && npm test -- src/background/service-worker.test.ts
```

Expected: FAIL — `api.explainQuiz` chưa được gọi lần nào (service worker chưa định tuyến).

- [ ] **Step 3: Thêm `case` vào `service-worker.ts`**

Thêm ngay sau khối `case 'ANSWER_QUIZ':`:

```ts
    case 'EXPLAIN_QUIZ':
      // Cũng như ANSWER_QUIZ: không refreshBadge. Quiz không chạm lịch SRS nên số thẻ đến
      // hạn không thể đổi vì một lượt xin giải thích.
      return client.explainQuiz({ quizItemId: request.quizItemId });
```

- [ ] **Step 4: Chạy test để xác nhận nó xanh**

```bash
cd extension && npm test -- src/background/service-worker.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add extension/src/background/service-worker.ts \
        extension/src/background/service-worker.test.ts
git commit -m "feat(ext): định tuyến EXPLAIN_QUIZ qua service worker"
```

---

### Task 9: Nút "Giải thích" và ba khối hiển thị trong QuizTab

**Files:**
- Modify: `extension/src/sidepanel/QuizTab.tsx`
- Test: `extension/src/sidepanel/QuizTab.test.tsx`

- [ ] **Step 1: Viết test thất bại — mở rộng helper và thêm 7 test**

Trong `QuizTab.test.tsx`:

(a) thêm `QuizExplanation` vào import type:

```ts
import type { AnswerResult, QuizExplanation, QuizItemDto } from '../shared/types';
```

(b) thêm hằng ngay sau `const CORRECT: AnswerResult = …`:

```ts
const EXPLANATION: QuizExplanation = {
  explanation: '"mitigate" đi với "impact"; "reduce" nhạt hơn.',
  answerMeaning: 'mitigate = giảm nhẹ',
  sentenceEn: 'Governments must mitigate the effects of climate change.',
  sentenceVi: 'Các chính phủ phải giảm nhẹ tác động của biến đổi khí hậu.',
};
```

(c) mở rộng `mockBackend` để phục vụ luôn `EXPLAIN_QUIZ`:

```ts
function mockBackend(opts: {
  generate?: (request: Sent) => unknown;
  answer?: (request: Sent) => unknown;
  explain?: (request: Sent) => unknown;
} = {}) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: Sent) => {
      if (request.type === 'GENERATE_QUIZ') {
        return opts.generate ? opts.generate(request) : { ok: true, data: [] };
      }
      if (request.type === 'ANSWER_QUIZ') {
        return opts.answer ? opts.answer(request) : { ok: true, data: CORRECT };
      }
      if (request.type === 'EXPLAIN_QUIZ') {
        return opts.explain ? opts.explain(request) : { ok: true, data: EXPLANATION };
      }
      return { ok: true, data: null };
    },
  );
}
```

(d) thêm nguyên khối describe này vào cuối file, ngay trước dấu `});` đóng
`describe('QuizTab', …)`:

```ts
  /* ================= Giải thích đáp án ================= */

  describe('giải thích đáp án', () => {
    /** Dựng một đề đúng hai câu FILL_BLANK rồi trả lời câu đầu. */
    async function answerFirstFillBlank(opts: {
      answer?: (request: Sent) => unknown;
      explain?: (request: Sent) => unknown;
    } = {}) {
      mockBackend({
        generate: (r) => (r.quizType === 'FILL_BLANK'
          ? { ok: true, data: [fillBlank(1), fillBlank(2)] }
          : { ok: true, data: [] }),
        answer: opts.answer,
        explain: opts.explain,
      });
      render(<QuizTab />);
      await generateOnly('Điền từ');

      await userEvent.type(await screen.findByLabelText('Từ cần điền'), 'reduce');
      await userEvent.click(screen.getByRole('button', { name: 'Nộp' }));
      await screen.findByRole('button', { name: 'Giải thích' });
    }

    it('chưa trả lời thì KHÔNG có nút Giải thích — nó tiết lộ đáp án', async () => {
      mockBackend({
        generate: (r) => (r.quizType === 'FILL_BLANK'
          ? { ok: true, data: [fillBlank(1)] }
          : { ok: true, data: [] }),
      });
      render(<QuizTab />);
      await generateOnly('Điền từ');
      await screen.findByLabelText('Từ cần điền');

      expect(screen.queryByRole('button', { name: 'Giải thích' })).not.toBeInTheDocument();
    });

    it('trả lời ĐÚNG vẫn có nút Giải thích — đoán trúng cũng cần biết vì sao', async () => {
      await answerFirstFillBlank({ answer: () => ({ ok: true, data: CORRECT }) });

      expect(screen.getByRole('button', { name: 'Giải thích' })).toBeEnabled();
    });

    it('bấm Giải thích gửi EXPLAIN_QUIZ đúng quizItemId và hiện đủ ba khối', async () => {
      await answerFirstFillBlank();

      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));

      await waitFor(() => expect(sentOf('EXPLAIN_QUIZ')).toHaveLength(1));
      // Body chỉ có quizItemId: câu trả lời KHÔNG được gửi kèm.
      expect(sentOf('EXPLAIN_QUIZ')[0]).toEqual({ type: 'EXPLAIN_QUIZ', quizItemId: 1 });

      expect(await screen.findByText(EXPLANATION.explanation)).toBeInTheDocument();
      expect(screen.getByText('mitigate = giảm nhẹ')).toBeInTheDocument();
      expect(screen.getByText(EXPLANATION.sentenceEn as string)).toBeInTheDocument();
      expect(screen.getByText(EXPLANATION.sentenceVi as string)).toBeInTheDocument();
      // Đã có giải thích thì nút biến mất — bấm lại chỉ tốn thêm một lượt gọi Gemini.
      expect(screen.queryByRole('button', { name: 'Giải thích' })).not.toBeInTheDocument();
    });

    it('cặp câu null thì KHÔNG render khối "Dịch câu"', async () => {
      await answerFirstFillBlank({
        explain: () => ({
          ok: true,
          data: {
            explanation: 'Bạn đã bỏ qua câu này.',
            answerMeaning: 'mitigate = giảm nhẹ',
            sentenceEn: null,
            sentenceVi: null,
          } satisfies QuizExplanation,
        }),
      });

      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));

      expect(await screen.findByText('Bạn đã bỏ qua câu này.')).toBeInTheDocument();
      expect(screen.queryByText('Dịch câu')).not.toBeInTheDocument();
    });

    it('lỗi hiện thông báo và nút Giải thích vẫn bấm lại được', async () => {
      let calls = 0;
      await answerFirstFillBlank({
        explain: () => {
          calls += 1;
          return calls === 1
            ? { ok: false, error: { code: 'GEMINI_UNAVAILABLE', message: 'Gemini đang bận.', retryable: true } }
            : { ok: true, data: EXPLANATION };
        },
      });

      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));

      expect(await screen.findByRole('alert')).toHaveTextContent('Gemini đang bận.');
      const retry = screen.getByRole('button', { name: 'Giải thích' });
      expect(retry).toBeEnabled();

      await userEvent.click(retry);

      expect(await screen.findByText(EXPLANATION.explanation)).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('đang giải thích thì nút Tiếp bị KHOÁ — response về muộn sẽ ghi nhầm sang câu sau', async () => {
      let release!: (value: unknown) => void;
      await answerFirstFillBlank({
        explain: () => new Promise((resolve) => { release = resolve; }),
      });

      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));

      expect(await screen.findByRole('button', { name: 'Đang giải thích…' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Tiếp' })).toBeDisabled();

      release({ ok: true, data: EXPLANATION });
      await screen.findByText(EXPLANATION.explanation);
      expect(screen.getByRole('button', { name: 'Tiếp' })).toBeEnabled();
    });

    it('sang câu mới thì khối giải thích biến sạch', async () => {
      await answerFirstFillBlank();
      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));
      await screen.findByText(EXPLANATION.explanation);

      await userEvent.click(screen.getByRole('button', { name: 'Tiếp' }));

      expect(screen.queryByText(EXPLANATION.explanation)).not.toBeInTheDocument();
      expect(screen.queryByText('Giải thích')).not.toBeInTheDocument();
      expect(await screen.findByLabelText('Từ cần điền')).toHaveValue('');
    });
  });
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd extension && npm test -- src/sidepanel/QuizTab.test.tsx
```

Expected: FAIL — bảy test mới không tìm thấy nút `Giải thích`.

- [ ] **Step 3: Sửa `QuizTab.tsx`**

(a) thêm `QuizExplanation` vào import type ở dòng 3:

```ts
import type { AnswerResult, ApiError, QuizExplanation, QuizItemDto, QuizType } from '../shared/types';
```

(b) thêm ba state ngay sau `const [answerError, setAnswerError] = useState<ApiError | null>(null);`:

```ts
  /**
   * MỘT ô chứ không phải mảng song song với `results`: điều hướng chỉ đi tới — `next()`
   * không có đường lùi — nên không bao giờ quay lại câu cũ. `results` là mảng vì màn tổng
   * kết đếm số câu đúng; giải thích không vào tổng kết.
   */
  const [explanation, setExplanation] = useState<QuizExplanation | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<ApiError | null>(null);
```

(c) trong `generate()`, ngay sau `setAnswerError(null);`, thêm:

```ts
    setExplanation(null);
    setExplainError(null);
```

(d) thêm hàm `explain()` ngay sau `submit()`:

```ts
  async function explain() {
    const item = items[index];
    if (!item || explaining) return;

    setExplaining(true);
    setExplainError(null);
    const response = await sendToBackground({ type: 'EXPLAIN_QUIZ', quizItemId: item.id });
    setExplaining(false);

    if (response.ok) {
      setExplanation(response.data);
    } else {
      setExplainError(response.error);
    }
  }
```

(e) thay `next()` và `reset()`:

```ts
  function next() {
    setDraft('');
    setAnswerError(null);
    setExplanation(null);
    setExplainError(null);
    setIndex((i) => i + 1);
  }

  function reset() {
    setItems([]);
    setResults([]);
    setIndex(0);
    setDraft('');
    setGenerated(false);
    setWarnings([]);
    setError(null);
    setAnswerError(null);
    setExplanation(null);
    setExplainError(null);
  }
```

(f) trong khối `{answered && (…)}` ở cuối component, thay nguyên nút "Tiếp" hiện tại:

```tsx
          <button type="button" className="quiz-next" onClick={next}>
            {index + 1 < items.length ? 'Tiếp' : 'Xem kết quả'}
          </button>
```

bằng:

```tsx
          {!explanation && (
            <button
              type="button"
              className="quiz-explain"
              disabled={explaining}
              onClick={() => void explain()}
            >
              {explaining ? 'Đang giải thích…' : 'Giải thích'}
            </button>
          )}

          {explainError && (
            <p className="status bad" role="alert">
              {explainError.message} Bấm "Giải thích" để thử lại.
            </p>
          )}

          {explanation && (
            <div className="quiz-explanation">
              <h3>Giải thích</h3>
              <p>{explanation.explanation}</p>

              <h3>Nghĩa đáp án</h3>
              <p>{explanation.answerMeaning}</p>

              {/*
                sentenceEn và sentenceVi là MỘT CẶP — backend không bao giờ gửi một nửa.
                Kiểm cả hai vừa để TypeScript hẹp được kiểu, vừa để một nửa lọt qua (nếu
                hợp đồng vỡ) không render ra một khối trống.
              */}
              {explanation.sentenceEn && explanation.sentenceVi && (
                <>
                  <h3>Dịch câu</h3>
                  <p className="quiz-sentence-en">{explanation.sentenceEn}</p>
                  <p>{explanation.sentenceVi}</p>
                </>
              )}
            </div>
          )}

          {/*
            Khoá nút Tiếp trong lúc đang giải thích. Không khoá thì bấm Tiếp khi request
            đang bay sẽ làm response về muộn ghi giải thích của câu cũ lên câu mới — sai
            câu, và không có lỗi nào nổ ra. Người vừa bấm "Giải thích" là người đang muốn
            đọc, nên chờ một hai giây không mất gì; response lỗi cũng kết thúc `explaining`
            nên không có đường kẹt vĩnh viễn.
          */}
          <button
            type="button"
            className="quiz-next"
            disabled={explaining}
            onClick={next}
          >
            {index + 1 < items.length ? 'Tiếp' : 'Xem kết quả'}
          </button>
```

- [ ] **Step 4: Chạy test để xác nhận nó xanh**

```bash
cd extension && npm test -- src/sidepanel/QuizTab.test.tsx
```

Expected: PASS — toàn bộ test trong file.

- [ ] **Step 5: Commit**

```bash
git add extension/src/sidepanel/QuizTab.tsx extension/src/sidepanel/QuizTab.test.tsx
git commit -m "feat(ext): nút Giải thích và ba khối kết quả trong QuizTab"
```

---

### Task 10: CSS và kiểm tra toàn bộ

**Files:**
- Modify: `extension/src/sidepanel/styles.css`

- [ ] **Step 1: Thêm CSS**

Thêm ngay sau khối `.quiz-skip:disabled { … }`:

```css
/* Giải thích là hành động phụ, bấm mới gọi — nhẹ hơn nút Tiếp để không tranh chỗ với nó. */
.quiz-explain {
  width: 100%;
  margin-top: 10px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--surface);
  color: var(--text-2);
  font: inherit;
  font-size: 12.5px;
  font-weight: 540;
  cursor: pointer;
}
.quiz-explain:hover:not(:disabled) { background: var(--surface-2); color: var(--text); }
.quiz-explain:disabled { opacity: 0.6; cursor: default; }

.quiz-explanation { margin-top: 12px; }
.quiz-explanation h3 {
  margin: 12px 0 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-3);
}
.quiz-explanation h3:first-child { margin-top: 0; }
.quiz-explanation p { margin: 0; font-size: 13.5px; line-height: 1.55; }

/* Câu tiếng Anh đứng ngay trên bản dịch — nghiêng để mắt tách được hai thứ tiếng. */
.quiz-explanation .quiz-sentence-en {
  margin-bottom: 3px;
  color: var(--text-2);
  font-style: italic;
}
```

- [ ] **Step 2: Chạy toàn bộ test extension**

```bash
cd extension && npm test
```

Expected: PASS — toàn bộ.

- [ ] **Step 3: Chạy type check + build**

```bash
cd extension && npm run build
```

Expected: PASS. Đây là nơi DUY NHẤT chạy type check — test xanh mà build đỏ vẫn là hỏng.

- [ ] **Step 4: Chạy toàn bộ test backend**

```bash
cd backend && mvn test
```

Expected: PASS — toàn bộ. (Cần Docker chạy sẵn cho Testcontainers.)

- [ ] **Step 5: Commit**

```bash
git add extension/src/sidepanel/styles.css
git commit -m "style(ext): khối giải thích đáp án trong màn quiz"
```

---

## Kiểm tra thủ công cuối cùng

Không thay lời cho ba lệnh test ở trên, nhưng đáng chạy một lượt thật vì đây là tính năng
người dùng nhìn thấy:

```bash
docker compose up -d --build
curl http://127.0.0.1:8080/api/health     # geminiConfigured phải là true
```

Nạp lại extension trong `chrome://extensions`, mở side panel → tab Quiz → Tạo đề → trả lời
một câu **sai** → bấm `Giải thích`. Kỳ vọng: hiện đủ ba khối, phần giải thích nhắc đúng thứ
vừa chọn/điền, và nút `Tiếp` bị khoá trong lúc chờ.
