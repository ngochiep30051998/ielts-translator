# Màn ôn tập dạng chọn đáp án — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đổi màn ôn tập SRS từ thẻ lật tự chấm sang trắc nghiệm bốn lựa chọn trộn hai chiều EN↔VI, rating suy ra từ đúng/sai cộng thời gian trả lời.

**Architecture:** Backend thêm bảng `srs_distractor` cache mồi nhử do Gemini sinh, sinh nền qua `@TransactionalEventListener(AFTER_COMMIT) + @Async` bám vào `VocabEntrySavedEvent` đã có. `CardDto` thêm hai mảng mồi nhử; không thêm endpoint nào. Extension dựng câu hỏi và suy ra rating trong module thuần `shared/mcq.ts`, `ReviewTab` chỉ còn là lớp vỏ hiển thị.

**Tech Stack:** Java 21, Spring Boot 3.4.1 (Web MVC, JPA, Flyway, `@EnableAsync`), Postgres 16, hypersistence-utils; React 18 + TypeScript 5.7, Vite 5 + CRXJS, Vitest + RTL.

**Spec:** [`docs/superpowers/specs/2026-08-06-srs-mcq-review-design.md`](../specs/2026-08-06-srs-mcq-review-design.md)

## Global Constraints

- Comment code, message lỗi, text hiển thị viết bằng **tiếng Việt đủ dấu**. Tên class/biến/hàm/package giữ tiếng Anh. Lưu UTF-8.
- **Không Lombok.** Constructor injection thủ công, `record` cho DTO, field `final` khi được.
- **Không thêm dependency mới.** `@EnableAsync` và `ThreadPoolTaskExecutor` là Spring core, không phải dependency mới.
- Side panel và Options **không bao giờ** gọi HTTP trực tiếp — mọi request qua service worker.
- `shared/types.ts` là bản gương của DTO backend. Đừng bịa field backend không có.
- Mọi lỗi API hình dạng `{ code, message, retryable }`. **Không thêm `ErrorCode` mới** — `GlobalExceptionHandler.statusFor()` là switch exhaustive.
- Sửa nội dung file `resources/prompts/*.md` **phải tăng `version:`** ở đầu file.
- Migration Flyway **append-only**. Không sửa `V1`–`V3`. Entity JPA phải khớp schema (`ddl-auto: validate` fail khi lệch).
- `vocabulary` **không** import gì từ `srs`. `srs` được phép import `vocabulary`. Kiểm chứng: `grep -r "ieltstranslator.srs" backend/src/main/java/com/hiepnn/ieltstranslator/vocabulary/` phải rỗng.
- Surefire include cả `**/*Test.java` (unit, không cần Docker) và `**/*IT.java` (integration, kế thừa `AbstractPostgresIT`). **Đặt sai tên file = test bị bỏ qua im lặng.**
- `npm run build` là nơi **duy nhất** chạy type check (`tsc --noEmit && vite build`). Test xanh mà build đỏ vẫn là hỏng — luôn chạy cả hai trước khi báo xong.
- TypeScript bật `strict` **và** `noUnusedLocals`.
- **Không bao giờ chạy `docker compose down -v`** — xoá volume `ielts_pgdata` là xoá sạch sổ từ vựng.
- `mvn test` cần Docker chạy sẵn cho Testcontainers.
- Nhánh hiện tại là `main`. Hỏi trước khi commit.

## File Structure

```
backend/src/main/java/com/hiepnn/ieltstranslator/
├── common/AsyncConfig.java                 ← mới: @EnableAsync + srsTaskExecutor
├── translation/PromptLoader.java           ← sửa: thêm load(String)
├── translation/PromptTemplate.java         ← sửa: thêm render(Map)
└── srs/
    ├── DistractorSet.java                  ← mới: record hai mảng mồi nhử
    ├── DistractorValidator.java            ← mới: hàm thuần, loại output rác
    ├── SrsDistractor.java                  ← mới: entity
    ├── SrsDistractorRepository.java        ← mới
    ├── DistractorGenerator.java            ← mới: listener async + gọi Gemini
    ├── SrsService.java                     ← sửa: nạp mồi nhử vào DTO + bù nền
    └── dto/CardDto.java                    ← sửa: thêm 2 field

backend/src/main/resources/
├── db/migration/V4__srs_distractor.sql     ← mới
└── prompts/srs-distractors.md              ← mới

backend/src/test/java/com/hiepnn/ieltstranslator/
├── translation/PromptLoaderTest.java       ← sửa: test load(String)
└── srs/
    ├── DistractorValidatorTest.java        ← mới: unit, không Docker
    ├── SrsDistractorMigrationIT.java       ← mới
    ├── DistractorGeneratorIT.java          ← mới
    └── SrsControllerIT.java                ← sửa: hình dạng CardDto mới

extension/src/
├── shared/types.ts                         ← sửa: CardDto thêm 2 field
├── shared/mcq.ts                           ← mới: buildQuestion + ratingFor
├── shared/mcq.test.ts                      ← mới
├── sidepanel/ReviewTab.tsx                 ← viết lại
├── sidepanel/ReviewTab.test.tsx            ← viết lại
└── sidepanel/styles.css                    ← sửa: style lựa chọn

README.md                                   ← sửa: mục "Ôn tập"
docs/superpowers/specs/2026-08-06-phase2-3-srs-quiz-design.md  ← sửa: ghi chú mục 2.9
```

**Không đổi:** `SrsScheduler`, `SrsCard`, `ReviewLog`, `SrsCardCreator`, `SrsController`, `V3`, `shared/messages.ts`, `background/*`, `manifest.config.ts`, `options/*`.

---

### Task 1: Prompt mồi nhử và `DistractorValidator`

Toàn bộ task này là code thuần, **không cần Docker**. Đây là phần dễ sai nhất về mặt logic nên làm trước và chốt bằng test bảng.

**Files:**
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/translation/PromptTemplate.java`
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/translation/PromptLoader.java:22-31`
- Create: `backend/src/main/resources/prompts/srs-distractors.md`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/srs/DistractorSet.java`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/srs/DistractorValidator.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/srs/DistractorValidatorTest.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/translation/PromptLoaderTest.java`

**Interfaces:**
- Consumes: `PromptTemplate(String body, int version)` đã có.
- Produces:
  - `PromptLoader.load(String fileName)` → `PromptTemplate` (fileName là tên file trong `resources/prompts`, ví dụ `"srs-distractors.md"`)
  - `PromptTemplate.render(Map<String, String> vars)` → `String`
  - `record DistractorSet(List<String> viOptions, List<String> enOptions)`
  - `DistractorValidator.isValid(DistractorSet set, String meaningVi, String term)` → `boolean`

- [ ] **Step 1: Viết `DistractorSet`**

Tạo `backend/src/main/java/com/hiepnn/ieltstranslator/srs/DistractorSet.java`:

```java
package com.hiepnn.ieltstranslator.srs;

import java.util.List;

/**
 * Ba mồi nhử cho mỗi chiều hỏi. {@code viOptions} là nghĩa tiếng Việt sai (dùng cho
 * câu hỏi EN → VI), {@code enOptions} là từ tiếng Anh sai (dùng cho VI → EN).
 */
public record DistractorSet(List<String> viOptions, List<String> enOptions) {
}
```

- [ ] **Step 2: Viết test thất bại cho `DistractorValidator`**

Tạo `backend/src/test/java/com/hiepnn/ieltstranslator/srs/DistractorValidatorTest.java`:

```java
package com.hiepnn.ieltstranslator.srs;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DistractorValidatorTest {

    private final DistractorValidator validator = new DistractorValidator();

    private static final String MEANING = "giảm nhẹ";
    private static final String TERM = "mitigate";

    private static DistractorSet set(List<String> vi, List<String> en) {
        return new DistractorSet(vi, en);
    }

    private static DistractorSet valid() {
        return set(List.of("làm trầm trọng thêm", "phóng đại", "trì hoãn"),
                   List.of("aggravate", "exaggerate", "postpone"));
    }

    @Test
    @DisplayName("Bộ mồi nhử đủ 3 phần tử mỗi chiều, không trùng, không đụng đáp án đúng thì hợp lệ")
    void acceptsValidSet() {
        assertThat(validator.isValid(valid(), MEANING, TERM)).isTrue();
    }

    @Test
    @DisplayName("Thiếu phần tử thì loại")
    void rejectsTooFew() {
        assertThat(validator.isValid(
                set(List.of("làm trầm trọng thêm", "phóng đại"),
                    List.of("aggravate", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Thừa phần tử thì loại — Gemini trả 4 nghĩa là dấu hiệu nó hiểu sai đề")
    void rejectsTooMany() {
        assertThat(validator.isValid(
                set(List.of("a", "b", "c"),
                    List.of("aggravate", "exaggerate", "postpone", "delay")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Phần tử rỗng hoặc chỉ có khoảng trắng thì loại")
    void rejectsBlank() {
        assertThat(validator.isValid(
                set(List.of("làm trầm trọng thêm", "   ", "trì hoãn"),
                    List.of("aggravate", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Hai phần tử trùng nhau trong cùng một chiều thì loại")
    void rejectsDuplicatesWithinSide() {
        assertThat(validator.isValid(
                set(List.of("phóng đại", "Phóng Đại", "trì hoãn"),
                    List.of("aggravate", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Mồi nhử trùng nghĩa đúng thì loại — hai lựa chọn cùng đúng là giết bài ôn")
    void rejectsWhenViOptionEqualsMeaning() {
        assertThat(validator.isValid(
                set(List.of("  Giảm Nhẹ ", "phóng đại", "trì hoãn"),
                    List.of("aggravate", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("Mồi nhử trùng chính từ đang hỏi thì loại")
    void rejectsWhenEnOptionEqualsTerm() {
        assertThat(validator.isValid(
                set(List.of("làm trầm trọng thêm", "phóng đại", "trì hoãn"),
                    List.of("MITIGATE", "exaggerate", "postpone")),
                MEANING, TERM)).isFalse();
    }

    @Test
    @DisplayName("null ở bất kỳ đâu thì loại, không ném NPE")
    void rejectsNulls() {
        assertThat(validator.isValid(null, MEANING, TERM)).isFalse();
        assertThat(validator.isValid(set(null, List.of("a", "b", "c")), MEANING, TERM)).isFalse();
        assertThat(validator.isValid(
                set(Arrays.asList("a", null, "c"), List.of("x", "y", "z")),
                MEANING, TERM)).isFalse();
    }
}
```

- [ ] **Step 3: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=DistractorValidatorTest
```

Kỳ vọng: FAIL khi biên dịch — `DistractorValidator` chưa tồn tại.

- [ ] **Step 4: Viết `DistractorValidator`**

Tạo `backend/src/main/java/com/hiepnn/ieltstranslator/srs/DistractorValidator.java`:

```java
package com.hiepnn.ieltstranslator.srs;

import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Kiểm tra bộ mồi nhử Gemini trả về. Hàm thuần — không DB, không mạng.
 *
 * <p>Loại CẢ bộ khi có bất kỳ vi phạm nào, thay vì cố vá từng phần tử: bộ đã hỏng thì
 * phần còn lại cũng không đáng tin, và để lần sau sinh lại rẻ hơn nhiều so với việc
 * người học gặp một câu hỏi có hai đáp án cùng đúng.
 */
@Component
public class DistractorValidator {

    private static final int REQUIRED_COUNT = 3;

    public boolean isValid(DistractorSet set, String meaningVi, String term) {
        if (set == null) {
            return false;
        }
        return sideIsValid(set.viOptions(), meaningVi)
                && sideIsValid(set.enOptions(), term);
    }

    /** Một chiều hợp lệ khi đủ 3 phần tử, không rỗng, không trùng nhau, không trùng đáp án đúng. */
    private boolean sideIsValid(List<String> options, String correctAnswer) {
        if (options == null || options.size() != REQUIRED_COUNT) {
            return false;
        }
        Set<String> seen = new HashSet<>();
        String correct = normalise(correctAnswer);
        for (String option : options) {
            if (option == null || option.isBlank()) {
                return false;
            }
            String key = normalise(option);
            if (key.equals(correct) || !seen.add(key)) {
                return false;
            }
        }
        return true;
    }

    private String normalise(String value) {
        return value == null ? "" : value.strip().toLowerCase(Locale.ROOT);
    }
}
```

- [ ] **Step 5: Chạy test để xác nhận nó xanh**

```bash
cd backend && mvn test -Dtest=DistractorValidatorTest
```

Kỳ vọng: PASS, 8 test.

- [ ] **Step 6: Thêm `render(Map)` vào `PromptTemplate`**

Prompt mồi nhử cần bốn biến chứ không phải hai, nên `PromptTemplate` cần một `render` tổng quát. Thay toàn bộ nội dung `backend/src/main/java/com/hiepnn/ieltstranslator/translation/PromptTemplate.java`:

```java
package com.hiepnn.ieltstranslator.translation;

import java.util.Map;

public record PromptTemplate(String body, int version) {

    private static final String NO_CONTEXT = "(không có ngữ cảnh)";

    /** Thay mọi {{KHOÁ}} bằng giá trị tương ứng. Giá trị null coi như chuỗi rỗng. */
    public String render(Map<String, String> vars) {
        String out = body;
        for (Map.Entry<String, String> entry : vars.entrySet()) {
            String value = entry.getValue() == null ? "" : entry.getValue();
            out = out.replace("{{" + entry.getKey() + "}}", value);
        }
        return out;
    }

    public String render(String text, String context) {
        String safeContext = (context == null || context.isBlank()) ? NO_CONTEXT : context;
        return render(Map.of("TEXT", text == null ? "" : text, "CONTEXT", safeContext));
    }
}
```

- [ ] **Step 7: Viết test thất bại cho `PromptLoader.load(String)`**

`PromptLoaderTest` đã có sẵn field `private final PromptLoader loader = new PromptLoader();` ở dòng 15 — dùng đúng field đó.

Thêm hai import vào đầu file (file hiện chưa có `DisplayName` và `Map`):

```java
import org.junit.jupiter.api.DisplayName;
import java.util.Map;
```

Rồi thêm hai test vào cuối class:

```java
    @Test
    @DisplayName("load theo tên file đọc được prompt mồi nhử và lấy đúng version")
    void loadsByFileName() {
        PromptTemplate template = loader.load("srs-distractors.md");

        assertThat(template.version()).isEqualTo(1);
        assertThat(template.body()).contains("{{TERM}}", "{{MEANING_VI}}");
    }

    @Test
    @DisplayName("render(Map) thay đúng mọi khoá")
    void rendersEveryPlaceholder() {
        String rendered = loader.load("srs-distractors.md")
                .render(Map.of("TERM", "mitigate", "MEANING_VI", "giảm nhẹ",
                               "POS", "verb", "DEFINITION_EN", "to make less severe"));

        assertThat(rendered).contains("mitigate", "giảm nhẹ", "verb", "to make less severe");
        assertThat(rendered).doesNotContain("{{");
    }
```

- [ ] **Step 8: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=PromptLoaderTest
```

Kỳ vọng: FAIL — chưa có method `load(String)` và chưa có file prompt.

- [ ] **Step 9: Thêm `load(String)` vào `PromptLoader`**

Thay ba method đầu của `backend/src/main/java/com/hiepnn/ieltstranslator/translation/PromptLoader.java` (dòng 22–31) bằng:

```java
    public PromptTemplate load(Direction direction, Mode mode) {
        return load(fileNameFor(direction, mode));
    }

    /**
     * @param fileName tên file trong {@code resources/prompts}, ví dụ "srs-distractors.md"
     */
    public PromptTemplate load(String fileName) {
        return cache.computeIfAbsent("prompts/" + fileName, this::readTemplate);
    }

    private String fileNameFor(Direction direction, Mode mode) {
        String dir = direction == Direction.EN_VI ? "en-vi" : "vi-en";
        String md = mode == Mode.WORD ? "word" : "sentence";
        return dir + "-" + md + ".md";
    }
```

> Chú ý: `fileNameFor` **bỏ** tiền tố `"prompts/"` vì `load(String)` đã thêm. Quên chỗ này thì đường dẫn thành `prompts/prompts/...` và bốn prompt dịch chết ngay.

- [ ] **Step 10: Viết file prompt**

Tạo `backend/src/main/resources/prompts/srs-distractors.md`:

```markdown
version: 1
---
Bạn đang tạo mồi nhử cho một câu trắc nghiệm từ vựng IELTS.

Từ: {{TERM}}
Từ loại: {{POS}}
Nghĩa tiếng Việt đúng: {{MEANING_VI}}
Định nghĩa tiếng Anh: {{DEFINITION_EN}}

Trả về JSON đúng schema đã cho, gồm hai mảng:

- vi_options: đúng 3 nghĩa tiếng Việt SAI, dùng làm đáp án nhiễu khi hỏi "{{TERM}} nghĩa là gì".
- en_options: đúng 3 từ tiếng Anh SAI, dùng làm đáp án nhiễu khi hỏi "từ nào có nghĩa {{MEANING_VI}}".

Quy tắc bắt buộc:
- Mồi nhử phải SAI rõ ràng nhưng KHÓ loại trừ: cùng từ loại, cùng miền nghĩa hoặc cùng
  ngữ cảnh học thuật với đáp án đúng. Ba nghĩa hoàn toàn không liên quan là mồi nhử tồi.
- KHÔNG được đồng nghĩa, gần nghĩa, hay là cách diễn đạt khác của đáp án đúng. Người học
  phải chỉ có đúng MỘT lựa chọn đúng.
- KHÔNG lặp lại chính {{TERM}} hay chính {{MEANING_VI}} dưới bất kỳ dạng nào.
- en_options phải là từ tiếng Anh có thật, cùng từ loại với {{TERM}}, độ khó tương đương.
- vi_options viết ngắn như một mục từ điển, tối đa 8 từ, không viết thành câu.
- Ba phần tử trong cùng một mảng phải khác nhau.
```

- [ ] **Step 11: Chạy test để xác nhận nó xanh**

```bash
cd backend && mvn test -Dtest=PromptLoaderTest,DistractorValidatorTest
```

Kỳ vọng: PASS cả hai class.

- [ ] **Step 12: Kiểm tra bốn prompt dịch chưa vỡ**

```bash
cd backend && mvn test
```

Kỳ vọng: 125 test cũ vẫn xanh (giờ thành 135 với test mới). Nếu `TranslationServiceIT` hoặc `TranslateControllerIT` đỏ thì gần như chắc chắn là lỗi tiền tố `prompts/` ở Step 9.

- [ ] **Step 13: Commit**

```bash
git add backend/src/main/java/com/hiepnn/ieltstranslator/srs/DistractorSet.java \
        backend/src/main/java/com/hiepnn/ieltstranslator/srs/DistractorValidator.java \
        backend/src/test/java/com/hiepnn/ieltstranslator/srs/DistractorValidatorTest.java \
        backend/src/main/java/com/hiepnn/ieltstranslator/translation/ \
        backend/src/test/java/com/hiepnn/ieltstranslator/translation/PromptLoaderTest.java \
        backend/src/main/resources/prompts/srs-distractors.md
git commit -m "feat(srs): prompt mồi nhử và validator loại output rác"
```

---

### Task 2: Migration `V4`, entity, repository

**Files:**
- Create: `backend/src/main/resources/db/migration/V4__srs_distractor.sql`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/srs/SrsDistractor.java`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/srs/SrsDistractorRepository.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/srs/SrsDistractorMigrationIT.java`

**Interfaces:**
- Consumes: `DistractorSet` (Task 1), `VocabEntry` đã có.
- Produces:
  - `SrsDistractor` với getter/setter: `getId()`, `getVocabEntry()/setVocabEntry(VocabEntry)`, `getViOptions()/setViOptions(List<String>)`, `getEnOptions()/setEnOptions(List<String>)`, `getPromptVersion()/setPromptVersion(int)`
  - `SrsDistractorRepository.findByVocabEntry_Id(Long)` → `Optional<SrsDistractor>`
  - `SrsDistractorRepository.findByVocabEntry_IdInAndPromptVersion(Collection<Long>, int)` → `List<SrsDistractor>`

- [ ] **Step 1: Viết migration**

Tạo `backend/src/main/resources/db/migration/V4__srs_distractor.sql`:

```sql
-- Mồi nhử cho câu trắc nghiệm ôn tập, do Gemini sinh một lần rồi cache.
-- prompt_version theo đúng nguyên tắc của lookup_cache: sửa prompt phải tăng version
-- trong file, bản ghi version cũ coi như không có và sẽ được sinh lại.
CREATE TABLE srs_distractor (
    id             BIGSERIAL   PRIMARY KEY,
    vocab_entry_id BIGINT      NOT NULL UNIQUE
                   REFERENCES vocab_entry(id) ON DELETE CASCADE,
    vi_options     JSONB       NOT NULL,
    en_options     JSONB       NOT NULL,
    prompt_version INT         NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> Không backfill. Sinh mồi nhử là gọi mạng; migration phải chạy được khi không có mạng
> và không có `GEMINI_API_KEY`. Từ cũ được bù dần ở Task 4.

- [ ] **Step 2: Viết entity**

Tạo `backend/src/main/java/com/hiepnn/ieltstranslator/srs/SrsDistractor.java`:

```java
package com.hiepnn.ieltstranslator.srs;

import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import org.hibernate.annotations.Type;

import java.time.Instant;
import java.util.List;

/** Mồi nhử đã cache cho một từ. Một từ đúng một bản ghi (UNIQUE trên vocab_entry_id). */
@Entity
@Table(name = "srs_distractor")
public class SrsDistractor {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "vocab_entry_id", nullable = false, unique = true)
    private VocabEntry vocabEntry;

    @Type(JsonType.class)
    @Column(name = "vi_options", columnDefinition = "jsonb", nullable = false)
    private List<String> viOptions;

    @Type(JsonType.class)
    @Column(name = "en_options", columnDefinition = "jsonb", nullable = false)
    private List<String> enOptions;

    @Column(name = "prompt_version", nullable = false)
    private int promptVersion;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    public Long getId() { return id; }
    public VocabEntry getVocabEntry() { return vocabEntry; }
    public void setVocabEntry(VocabEntry vocabEntry) { this.vocabEntry = vocabEntry; }
    public List<String> getViOptions() { return viOptions; }
    public void setViOptions(List<String> viOptions) { this.viOptions = viOptions; }
    public List<String> getEnOptions() { return enOptions; }
    public void setEnOptions(List<String> enOptions) { this.enOptions = enOptions; }
    public int getPromptVersion() { return promptVersion; }
    public void setPromptVersion(int promptVersion) { this.promptVersion = promptVersion; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
```

- [ ] **Step 3: Viết repository**

Tạo `backend/src/main/java/com/hiepnn/ieltstranslator/srs/SrsDistractorRepository.java`:

```java
package com.hiepnn.ieltstranslator.srs;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface SrsDistractorRepository extends JpaRepository<SrsDistractor, Long> {

    Optional<SrsDistractor> findByVocabEntry_Id(Long vocabEntryId);

    /**
     * Chỉ trả bản ghi còn hiệu lực. Lọc {@code promptVersion} ngay trong truy vấn là cách
     * làm mồi nhử cũ tự biến mất khi tăng version prompt, không cần xoá dữ liệu.
     */
    List<SrsDistractor> findByVocabEntry_IdInAndPromptVersion(Collection<Long> vocabEntryIds,
                                                              int promptVersion);
}
```

- [ ] **Step 4: Viết test thất bại cho migration**

Tạo `backend/src/test/java/com/hiepnn/ieltstranslator/srs/SrsDistractorMigrationIT.java`:

```java
package com.hiepnn.ieltstranslator.srs;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class SrsDistractorMigrationIT extends AbstractPostgresIT {

    @Autowired VocabEntryRepository vocab;
    @Autowired SrsDistractorRepository distractors;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper objectMapper;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM review_log");
        jdbc.update("DELETE FROM srs_card");
        jdbc.update("DELETE FROM srs_distractor");
        jdbc.update("DELETE FROM vocab_entry");
    }

    private VocabEntry saveWord(String term) {
        VocabEntry entry = new VocabEntry();
        entry.setTerm(term);
        entry.setLemma(term);
        entry.setLang("en");
        entry.setPos("verb");
        entry.setMeaningVi("nghĩa của " + term);
        entry.setCollocations(objectMapper.createArrayNode());
        entry.setExamples(objectMapper.createArrayNode());
        return vocab.save(entry);
    }

    @Test
    @DisplayName("Lưu và đọc lại được hai mảng JSONB")
    void roundTripsJsonbColumns() {
        VocabEntry entry = saveWord("mitigate");

        SrsDistractor d = new SrsDistractor();
        d.setVocabEntry(entry);
        d.setViOptions(List.of("làm trầm trọng thêm", "phóng đại", "trì hoãn"));
        d.setEnOptions(List.of("aggravate", "exaggerate", "postpone"));
        d.setPromptVersion(1);
        distractors.save(d);

        SrsDistractor loaded = distractors.findByVocabEntry_Id(entry.getId()).orElseThrow();
        assertThat(loaded.getViOptions()).containsExactly("làm trầm trọng thêm", "phóng đại", "trì hoãn");
        assertThat(loaded.getEnOptions()).containsExactly("aggravate", "exaggerate", "postpone");
        assertThat(loaded.getPromptVersion()).isEqualTo(1);
    }

    @Test
    @DisplayName("Lọc theo promptVersion: bản ghi version cũ coi như không có")
    void filtersByPromptVersion() {
        VocabEntry entry = saveWord("resilient");
        SrsDistractor d = new SrsDistractor();
        d.setVocabEntry(entry);
        d.setViOptions(List.of("a", "b", "c"));
        d.setEnOptions(List.of("x", "y", "z"));
        d.setPromptVersion(1);
        distractors.save(d);

        assertThat(distractors.findByVocabEntry_IdInAndPromptVersion(List.of(entry.getId()), 1))
                .hasSize(1);
        assertThat(distractors.findByVocabEntry_IdInAndPromptVersion(List.of(entry.getId()), 2))
                .isEmpty();
    }

    @Test
    @DisplayName("Xoá từ trong sổ thì mồi nhử cascade theo, không để lại rác")
    void cascadesOnVocabDelete() {
        VocabEntry entry = saveWord("scrutinise");
        SrsDistractor d = new SrsDistractor();
        d.setVocabEntry(entry);
        d.setViOptions(List.of("a", "b", "c"));
        d.setEnOptions(List.of("x", "y", "z"));
        d.setPromptVersion(1);
        distractors.save(d);

        jdbc.update("DELETE FROM vocab_entry WHERE id = ?", entry.getId());

        assertThat(distractors.count()).isZero();
    }
}
```

- [ ] **Step 5: Chạy test để xác nhận nó xanh**

```bash
cd backend && mvn test -Dtest=SrsDistractorMigrationIT
```

Kỳ vọng: PASS, 3 test. Docker phải đang chạy.

Nếu fail với `Schema-validation: wrong column type` thì `columnDefinition` của cột JSONB
không khớp — kiểm tra lại Step 2, hai cột phải là `jsonb` đúng chữ thường.

- [ ] **Step 6: Chạy toàn bộ test backend**

```bash
cd backend && mvn test
```

Kỳ vọng: mọi test cũ vẫn xanh. `ddl-auto: validate` chạy trên mọi IT nên entity lệch schema sẽ làm **tất cả** IT đỏ, không chỉ test mới.

- [ ] **Step 7: Commit**

```bash
git add backend/src/main/resources/db/migration/V4__srs_distractor.sql \
        backend/src/main/java/com/hiepnn/ieltstranslator/srs/SrsDistractor.java \
        backend/src/main/java/com/hiepnn/ieltstranslator/srs/SrsDistractorRepository.java \
        backend/src/test/java/com/hiepnn/ieltstranslator/srs/SrsDistractorMigrationIT.java
git commit -m "feat(srs): bảng srs_distractor, entity và repository"
```

---

### Task 3: `DistractorGenerator` — sinh nền, không chặn việc lưu từ

**Files:**
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/common/AsyncConfig.java`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/srs/DistractorGenerator.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/srs/DistractorGeneratorIT.java`

**Interfaces:**
- Consumes: `DistractorSet`, `DistractorValidator`, `PromptLoader.load(String)` (Task 1); `SrsDistractor`, `SrsDistractorRepository` (Task 2); `GeminiClient.generateJson(String, Map<String,Object>)`, `VocabEntrySavedEvent(VocabEntry entry)`, `VocabEntryRepository` đã có.
- Produces:
  - `DistractorGenerator.generateAsync(Long vocabEntryId)` → `void`, `@Async` — Task 4 gọi method này để bù mồi nhử.
  - `DistractorGenerator.currentPromptVersion()` → `int` — Task 4 dùng để lọc bản ghi còn hiệu lực.
  - Bean executor tên `"srsTaskExecutor"`.

- [ ] **Step 1: Viết `AsyncConfig`**

Tạo `backend/src/main/java/com/hiepnn/ieltstranslator/common/AsyncConfig.java`:

```java
package com.hiepnn.ieltstranslator.common;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;
import java.util.concurrent.ThreadPoolExecutor;

/**
 * Pool cho việc chạy nền của module srs (hiện chỉ có sinh mồi nhử).
 *
 * <p>Pool nhỏ và hàng đợi có chặn là cố ý: một đợt lưu hàng loạt không được phép biến
 * thành hàng trăm call Gemini song song. Khi hàng đợi đầy, {@code CallerRunsPolicy} bắt
 * chính luồng gọi chạy tác vụ — lúc đó việc lưu từ sẽ chậm lại, và đó là hành vi mong
 * muốn hơn so với âm thầm vứt tác vụ đi.
 */
@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean("srsTaskExecutor")
    public Executor srsTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(1);
        executor.setMaxPoolSize(2);
        executor.setQueueCapacity(50);
        executor.setThreadNamePrefix("srs-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();
        return executor;
    }
}
```

- [ ] **Step 2: Viết test thất bại**

Tạo `backend/src/test/java/com/hiepnn/ieltstranslator/srs/DistractorGeneratorIT.java`:

```java
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
import static org.mockito.Mockito.*;

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
        when(geminiClient.generateJson(anyString(), any())).thenReturn(objectMapper.readTree("""
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
        verify(geminiClient, never()).generateJson(anyString(), any());
        assertThat(distractors.count()).isZero();
    }

    @Test
    @DisplayName("Gemini lỗi thì từ vẫn nằm trong sổ, chỉ là chưa có mồi nhử")
    void geminiFailureDoesNotBreakSave() {
        when(geminiClient.generateJson(anyString(), any()))
                .thenThrow(AppException.of(ErrorCode.GEMINI_UNAVAILABLE, "Gemini chết"));

        SaveVocabResponse saved = vocabService.save(request("resilient", "adjective"));

        assertThat(saved.id()).isNotNull();
        assertThat(distractors.findByVocabEntry_Id(saved.id())).isEmpty();
    }

    @Test
    @DisplayName("Gemini trả bộ hỏng (trùng đáp án đúng) thì không lưu gì, để lần sau sinh lại")
    void rejectsInvalidSet() throws Exception {
        when(geminiClient.generateJson(anyString(), any())).thenReturn(objectMapper.readTree("""
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

        when(geminiClient.generateJson(anyString(), any())).thenReturn(objectMapper.readTree("""
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
```

> `awaitility` đã có sẵn trong classpath test của Spring Boot starter-test, không phải
> dependency mới. Nếu `mvn test` báo không tìm thấy `org.awaitility` thì thay bằng vòng
> lặp chờ thủ công — **không** thêm dependency vào `pom.xml`.

- [ ] **Step 3: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=DistractorGeneratorIT
```

Kỳ vọng: FAIL khi biên dịch — `DistractorGenerator` chưa tồn tại.

- [ ] **Step 4: Viết `DistractorGenerator`**

Tạo `backend/src/main/java/com/hiepnn/ieltstranslator/srs/DistractorGenerator.java`:

```java
package com.hiepnn.ieltstranslator.srs;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.translation.PromptLoader;
import com.hiepnn.ieltstranslator.translation.PromptTemplate;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntryRepository;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntrySavedEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Sinh mồi nhử cho câu trắc nghiệm ôn tập.
 *
 * <p>Vì sao KHÔNG gộp vào {@link SrsCardCreator}: creator chạy đồng bộ trong cùng
 * transaction với lệnh lưu từ. Gọi Gemini ở đó sẽ làm thao tác lưu treo tới 15 giây, và
 * Gemini lỗi sẽ rollback cả việc lưu từ. Ở đây phải là AFTER_COMMIT (từ đã nằm chắc
 * trong sổ trước khi gọi mạng) và {@code @Async} (response không chờ Gemini).
 */
@Component
public class DistractorGenerator {

    private static final Logger log = LoggerFactory.getLogger(DistractorGenerator.class);

    /** pos của một câu đầy đủ — câu không làm trắc nghiệm được. */
    private static final String PHRASE_POS = "phrase";
    private static final String PROMPT_FILE = "srs-distractors.md";

    private static final Map<String, Object> SCHEMA = Map.of(
            "type", "object",
            "properties", Map.of(
                    "vi_options", Map.of("type", "array", "items", Map.of("type", "string")),
                    "en_options", Map.of("type", "array", "items", Map.of("type", "string"))),
            "required", List.of("vi_options", "en_options"));

    /** Chặn xếp chồng call cho cùng một từ khi người dùng mở tab ôn nhiều lần. */
    private final Set<Long> inFlight = ConcurrentHashMap.newKeySet();

    private final VocabEntryRepository vocab;
    private final SrsDistractorRepository distractors;
    private final DistractorValidator validator;
    private final GeminiClient gemini;
    private final PromptLoader prompts;

    public DistractorGenerator(VocabEntryRepository vocab, SrsDistractorRepository distractors,
                               DistractorValidator validator, GeminiClient gemini,
                               PromptLoader prompts) {
        this.vocab = vocab;
        this.distractors = distractors;
        this.validator = validator;
        this.gemini = gemini;
        this.prompts = prompts;
    }

    public int currentPromptVersion() {
        return prompts.load(PROMPT_FILE).version();
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Async("srsTaskExecutor")
    public void onVocabEntrySaved(VocabEntrySavedEvent event) {
        generate(event.entry().getId());
    }

    /** Bù mồi nhử cho từ cũ hoặc cho lần Gemini hỏng. Gọi từ bean khác nên proxy @Async có tác dụng. */
    @Async("srsTaskExecutor")
    public void generateAsync(Long vocabEntryId) {
        generate(vocabEntryId);
    }

    private void generate(Long vocabEntryId) {
        if (vocabEntryId == null || !inFlight.add(vocabEntryId)) {
            return;
        }
        try {
            vocab.findById(vocabEntryId).ifPresent(this::generateFor);
        } catch (RuntimeException ex) {
            // Không ai đang đứng chờ việc này — log rồi thôi, lần mở tab ôn sau sẽ thử lại.
            log.warn("Không sinh được mồi nhử cho vocab id={}: {}", vocabEntryId, ex.toString());
        } finally {
            inFlight.remove(vocabEntryId);
        }
    }

    private void generateFor(VocabEntry entry) {
        if (PHRASE_POS.equals(entry.getPos())) {
            return;
        }

        PromptTemplate template = prompts.load(PROMPT_FILE);
        String prompt = template.render(Map.of(
                "TERM", nullToEmpty(entry.getTerm()),
                "POS", nullToEmpty(entry.getPos()),
                "MEANING_VI", nullToEmpty(entry.getMeaningVi()),
                "DEFINITION_EN", nullToEmpty(entry.getDefinitionEn())));

        JsonNode payload = gemini.generateJson(prompt, SCHEMA);
        DistractorSet set = new DistractorSet(
                readStrings(payload.path("vi_options")),
                readStrings(payload.path("en_options")));

        if (!validator.isValid(set, entry.getMeaningVi(), entry.getTerm())) {
            log.warn("Gemini trả bộ mồi nhử không hợp lệ cho '{}', bỏ qua", entry.getTerm());
            return;
        }

        SrsDistractor row = distractors.findByVocabEntry_Id(entry.getId())
                .orElseGet(SrsDistractor::new);
        row.setVocabEntry(entry);
        row.setViOptions(set.viOptions());
        row.setEnOptions(set.enOptions());
        row.setPromptVersion(template.version());
        distractors.save(row);
    }

    private List<String> readStrings(JsonNode array) {
        if (!array.isArray()) {
            return List.of();
        }
        List<String> out = new ArrayList<>(array.size());
        array.forEach(node -> out.add(node.asText(null)));
        return out;
    }

    private String nullToEmpty(String value) {
        return value == null ? "" : value;
    }
}
```

- [ ] **Step 5: Chạy test để xác nhận nó xanh**

```bash
cd backend && mvn test -Dtest=DistractorGeneratorIT
```

Kỳ vọng: PASS, 5 test.

Nếu test `generatesOnSave` timeout: kiểm tra `@EnableAsync` đã ở `AsyncConfig` và tên bean
executor khớp chuỗi `"srsTaskExecutor"` trong `@Async`.

- [ ] **Step 6: Kiểm tra ranh giới module chưa vỡ**

```bash
grep -r "ieltstranslator.srs" backend/src/main/java/com/hiepnn/ieltstranslator/vocabulary/
```

Kỳ vọng: **không in ra gì**. `srs` được import `vocabulary`, chiều ngược lại thì không.

- [ ] **Step 7: Chạy toàn bộ test backend**

```bash
cd backend && mvn test
```

Kỳ vọng: mọi test xanh. `@EnableAsync` ảnh hưởng toàn ứng dụng nên phải kiểm cả bộ, không
chỉ test mới.

- [ ] **Step 8: Commit**

```bash
git add backend/src/main/java/com/hiepnn/ieltstranslator/common/AsyncConfig.java \
        backend/src/main/java/com/hiepnn/ieltstranslator/srs/DistractorGenerator.java \
        backend/src/test/java/com/hiepnn/ieltstranslator/srs/DistractorGeneratorIT.java
git commit -m "feat(srs): sinh mồi nhử nền sau khi lưu từ, không chặn request"
```

---

### Task 4: `CardDto` mang mồi nhử, `SrsService` bù cho từ cũ

**Files:**
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/srs/dto/CardDto.java`
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/srs/SrsService.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/srs/SrsControllerIT.java`

**Interfaces:**
- Consumes: `SrsDistractorRepository.findByVocabEntry_IdInAndPromptVersion` (Task 2), `DistractorGenerator.generateAsync`, `DistractorGenerator.currentPromptVersion()` (Task 3).
- Produces: `CardDto` thêm hai field cuối `List<String> viDistractors`, `List<String> enDistractors` — Task 5 dựng bản gương TypeScript theo đúng hai tên này.

- [ ] **Step 1: Viết test thất bại**

Trong `backend/src/test/java/com/hiepnn/ieltstranslator/srs/SrsControllerIT.java`:

**a)** Thêm import và một `@MockitoBean`. Từ Task 4 trở đi, `SrsService.due()` bắn sinh mồi
nhử nền cho thẻ còn thiếu — không chặn `@MockitoBean GeminiClient` thì mỗi lần chạy test
sẽ có call HTTP thật ra Gemini bằng `test-key`, chậm và bẩn log:

```java
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
```

```java
    @MockitoBean GeminiClient geminiClient;
```

**b)** Thêm dòng dọn bảng mới vào `clean()`, **trước** dòng xoá `vocab_entry`:

```java
        jdbc.update("DELETE FROM srs_distractor");
```

**c)** Thêm test mới vào cuối class (dùng đúng helper `seed()` có sẵn ở dòng 39):

```java
    @Test
    @DisplayName("CardDto có hai mảng mồi nhử, rỗng khi chưa sinh")
    void cardDtoCarriesEmptyDistractorsWhenNotGenerated() throws Exception {
        seed();

        mockMvc.perform(get("/api/srs/due").param("limit", "10").param("newLimit", "30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].viDistractors").isArray())
                .andExpect(jsonPath("$[0].viDistractors").isEmpty())
                .andExpect(jsonPath("$[0].enDistractors").isArray())
                .andExpect(jsonPath("$[0].enDistractors").isEmpty());
    }
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd backend && mvn test -Dtest=SrsControllerIT
```

Kỳ vọng: FAIL — JSON không có field `viDistractors`.

- [ ] **Step 3: Thêm hai field vào `CardDto`**

Thay toàn bộ `backend/src/main/java/com/hiepnn/ieltstranslator/srs/dto/CardDto.java`:

```java
package com.hiepnn.ieltstranslator.srs.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.srs.CardState;

import java.time.LocalDate;
import java.util.List;

/**
 * Gộp sẵn dữ liệu vocab để side panel chỉ phải gọi một lượt cho cả xấp thẻ.
 *
 * <p>{@code viDistractors} / {@code enDistractors} rỗng nghĩa là mồi nhử chưa sinh kịp;
 * panel tự bù bằng thẻ khác trong hàng đợi chứ không coi đó là lỗi.
 */
public record CardDto(Long id, Long vocabEntryId, String term, String ipa, String pos,
                      String meaningVi, String definitionEn, String cefr, String bandLevel,
                      JsonNode collocations, JsonNode examples,
                      CardState state, LocalDate dueDate,
                      List<String> viDistractors, List<String> enDistractors) {
}
```

- [ ] **Step 4: Sửa `SrsService`**

Thay toàn bộ `backend/src/main/java/com/hiepnn/ieltstranslator/srs/SrsService.java`. Chỉ
`due()`, `toDto()` và constructor đổi; `stats()`, `review()`, `remainingNewToday()` giữ
nguyên từng dòng:

```java
package com.hiepnn.ieltstranslator.srs;

import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.srs.dto.CardDto;
import com.hiepnn.ieltstranslator.srs.dto.ReviewResponse;
import com.hiepnn.ieltstranslator.srs.dto.SrsStatsDto;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class SrsService {

    /** Số từ được bù mồi nhử mỗi lần mở tab ôn. Chặn để một sổ lớn không bắn cả trăm call. */
    private static final int MAX_BACKFILL_PER_CALL = 10;

    private final SrsCardRepository cards;
    private final ReviewLogRepository logs;
    private final SrsScheduler scheduler;
    private final SrsDistractorRepository distractors;
    private final DistractorGenerator generator;

    public SrsService(SrsCardRepository cards, ReviewLogRepository logs, SrsScheduler scheduler,
                      SrsDistractorRepository distractors, DistractorGenerator generator) {
        this.cards = cards;
        this.logs = logs;
        this.scheduler = scheduler;
        this.distractors = distractors;
        this.generator = generator;
    }

    /**
     * Hàng đợi ôn: TOÀN BỘ thẻ đã đến hạn (không giới hạn), rồi mới tới thẻ mới trong
     * phần hạn mức còn lại của ngày. Tổng cắt ở {@code limit}.
     */
    @Transactional(readOnly = true)
    public List<CardDto> due(int limit, int newLimit) {
        List<SrsCard> dueCards = cards.findDue(
                LocalDate.now(), CardState.NEW, PageRequest.of(0, limit));

        List<SrsCard> queue = new ArrayList<>(dueCards);
        int room = Math.min(limit - dueCards.size(), remainingNewToday(newLimit));
        if (room > 0) {
            queue.addAll(cards.findNewCards(CardState.NEW, PageRequest.of(0, room)));
        }

        Map<Long, SrsDistractor> byVocabId = loadFreshDistractors(queue);
        requestMissing(queue, byVocabId);

        return queue.stream().map(card -> toDto(card, byVocabId)).toList();
    }

    @Transactional(readOnly = true)
    public SrsStatsDto stats(int newLimit) {
        long dueNow = cards.countDue(LocalDate.now(), CardState.NEW);
        long newTotal = cards.countByState(CardState.NEW);
        long newAllowed = Math.min(newTotal, remainingNewToday(newLimit));
        return new SrsStatsDto(dueNow + newAllowed, newTotal, cards.countLearned());
    }

    @Transactional
    public ReviewResponse review(Long cardId, Rating rating) {
        SrsCard card = cards.findById(cardId).orElseThrow(
                () -> AppException.of(ErrorCode.NOT_FOUND, "Không tìm thấy thẻ id=" + cardId));

        int prevInterval = card.getIntervalDays();
        Schedule next = scheduler.next(card, rating, LocalDate.now());

        card.setEaseFactor(next.easeFactor());
        card.setIntervalDays(next.intervalDays());
        card.setRepetitions(next.repetitions());
        card.setLapses(next.lapses());
        card.setDueDate(next.dueDate());
        card.setState(next.state());

        ReviewLog log = new ReviewLog();
        log.setCard(card);
        log.setRating(rating);
        log.setPrevInterval(prevInterval);
        log.setNewInterval(next.intervalDays());
        logs.save(log);

        return new ReviewResponse(next.dueDate(), next.intervalDays(), next.easeFactor());
    }

    /** Chỉ lấy mồi nhử còn hiệu lực với version prompt hiện hành. */
    private Map<Long, SrsDistractor> loadFreshDistractors(List<SrsCard> queue) {
        if (queue.isEmpty()) {
            return Map.of();
        }
        List<Long> vocabIds = queue.stream().map(c -> c.getVocabEntry().getId()).toList();
        Map<Long, SrsDistractor> byVocabId = new HashMap<>();
        for (SrsDistractor d : distractors.findByVocabEntry_IdInAndPromptVersion(
                vocabIds, generator.currentPromptVersion())) {
            byVocabId.put(d.getVocabEntry().getId(), d);
        }
        return byVocabId;
    }

    /**
     * Bắn sinh nền cho thẻ chưa có mồi nhử rồi trả hàng đợi về NGAY — không chờ. Lượt ôn
     * lúc này vẫn chạy được nhờ panel tự bù mồi nhử từ thẻ khác; lượt sau đã có bộ thật.
     *
     * <p>Đây cũng là đường bù cho từ lưu từ trước khi có tính năng này, và cho mọi từ có
     * mồi nhử hết hiệu lực sau khi tăng version prompt.
     */
    private void requestMissing(List<SrsCard> queue, Map<Long, SrsDistractor> byVocabId) {
        int requested = 0;
        for (SrsCard card : queue) {
            if (requested >= MAX_BACKFILL_PER_CALL) {
                return;
            }
            Long vocabId = card.getVocabEntry().getId();
            if (!byVocabId.containsKey(vocabId)) {
                generator.generateAsync(vocabId);
                requested++;
            }
        }
    }

    /** Hạn mức từ mới còn lại của hôm nay, không bao giờ âm. */
    private int remainingNewToday(int newLimit) {
        Instant startOfDay = LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant();
        long introduced = logs.countIntroducedSince(startOfDay);
        return (int) Math.max(0L, newLimit - introduced);
    }

    private CardDto toDto(SrsCard card, Map<Long, SrsDistractor> byVocabId) {
        VocabEntry v = card.getVocabEntry();
        SrsDistractor d = byVocabId.get(v.getId());
        List<String> vi = d == null ? List.of() : d.getViOptions();
        List<String> en = d == null ? List.of() : d.getEnOptions();
        return new CardDto(card.getId(), v.getId(), v.getTerm(), v.getIpa(), v.getPos(),
                v.getMeaningVi(), v.getDefinitionEn(), v.getCefr(), v.getBandLevel(),
                v.getCollocations(), v.getExamples(), card.getState(), card.getDueDate(),
                vi, en);
    }
}
```

- [ ] **Step 5: Chạy test để xác nhận nó xanh**

```bash
cd backend && mvn test -Dtest=SrsControllerIT,SrsServiceIT
```

Kỳ vọng: PASS. `SrsServiceIT` có thể đỏ ở chỗ dựng `CardDto` trực tiếp — nếu vậy, sửa test
theo constructor mới (thêm `List.of(), List.of()` ở cuối), **không** đổi thứ tự field.

- [ ] **Step 6: Chạy toàn bộ test backend**

```bash
cd backend && mvn test
```

Kỳ vọng: toàn bộ xanh.

- [ ] **Step 7: Commit**

```bash
git add backend/src/main/java/com/hiepnn/ieltstranslator/srs/ \
        backend/src/test/java/com/hiepnn/ieltstranslator/srs/
git commit -m "feat(srs): CardDto mang mồi nhử, bù nền cho thẻ còn thiếu"
```

---

### Task 5: `shared/mcq.ts` — dựng câu hỏi và suy ra rating

Từ đây trở đi là extension. **Không cần Docker.**

**Files:**
- Modify: `extension/src/shared/types.ts:99-113`
- Create: `extension/src/shared/mcq.ts`
- Test: `extension/src/shared/mcq.test.ts`

**Interfaces:**
- Consumes: `CardDto` (bản gương của Task 4), `Rating` đã có trong `shared/types.ts`.
- Produces:
  - `type QuizDirection = 'EN_VI' | 'VI_EN'`
  - `interface Question { direction: QuizDirection; card: CardDto; options: string[]; correctIndex: number }`
  - `buildQuestion(card: CardDto, pool: CardDto[], random: () => number): Question | null`
  - `ratingFor(correct: boolean, elapsedMs: number): Rating`

- [ ] **Step 1: Thêm hai field vào `CardDto` phía extension**

Trong `extension/src/shared/types.ts`, thêm hai dòng cuối vào interface `CardDto` (ngay
sau `dueDate: string;`):

```ts
  viDistractors: string[];
  enDistractors: string[];
```

- [ ] **Step 2: Viết test thất bại**

Tạo `extension/src/shared/mcq.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { buildQuestion, ratingFor } from './mcq';
import type { CardDto } from './types';

function card(id: number, term: string, vi: string[] = [], en: string[] = []): CardDto {
  return {
    id, vocabEntryId: id * 10, term, ipa: '/test/', pos: 'verb',
    meaningVi: `nghĩa của ${term}`, definitionEn: null, cefr: null, bandLevel: null,
    collocations: [], examples: [], state: 'NEW', dueDate: '2026-08-06',
    viDistractors: vi, enDistractors: en,
  };
}

/** random() trả cùng một giá trị mỗi lần gọi — đủ để test tất định, không cần seed thật. */
const fixedRandom = (value: number) => () => value;

const FULL = card(1, 'mitigate',
  ['làm trầm trọng thêm', 'phóng đại', 'trì hoãn'],
  ['aggravate', 'exaggerate', 'postpone']);

describe('ratingFor', () => {
  it('sai thì luôn là AGAIN, bất kể nhanh chậm', () => {
    expect(ratingFor(false, 1_000)).toBe('AGAIN');
    expect(ratingFor(false, 90_000)).toBe('AGAIN');
  });

  it('đúng dưới 5s là EASY', () => {
    expect(ratingFor(true, 4_999)).toBe('EASY');
  });

  it('đúng từ 5s tới dưới 15s là GOOD', () => {
    expect(ratingFor(true, 5_000)).toBe('GOOD');
    expect(ratingFor(true, 14_999)).toBe('GOOD');
  });

  it('đúng từ 15s tới 60s là HARD', () => {
    expect(ratingFor(true, 15_000)).toBe('HARD');
    expect(ratingFor(true, 60_000)).toBe('HARD');
  });

  it('đúng trên 60s quay lại GOOD — quá lâu là rời máy, không phải nhớ chật vật', () => {
    expect(ratingFor(true, 60_001)).toBe('GOOD');
  });
});

describe('buildQuestion', () => {
  it('chiều EN_VI hỏi nghĩa: đáp án đúng là meaningVi, mồi nhử là viDistractors', () => {
    const q = buildQuestion(FULL, [], fixedRandom(0));

    expect(q).not.toBeNull();
    expect(q!.direction).toBe('EN_VI');
    expect(q!.options).toHaveLength(4);
    expect(q!.options[q!.correctIndex]).toBe('nghĩa của mitigate');
    expect(q!.options).toEqual(expect.arrayContaining(['phóng đại']));
  });

  it('chiều VI_EN hỏi từ: đáp án đúng là term, mồi nhử là enDistractors', () => {
    const q = buildQuestion(FULL, [], fixedRandom(0.99));

    expect(q!.direction).toBe('VI_EN');
    expect(q!.options[q!.correctIndex]).toBe('mitigate');
    expect(q!.options).toEqual(expect.arrayContaining(['aggravate']));
  });

  it('thiếu mồi nhử thì bù bằng thẻ khác trong hàng đợi', () => {
    const bare = card(1, 'mitigate');
    const pool = [bare, card(2, 'resilient'), card(3, 'scrutinise'), card(4, 'coherent')];

    const q = buildQuestion(bare, pool, fixedRandom(0));

    expect(q!.options).toHaveLength(4);
    expect(q!.options[q!.correctIndex]).toBe('nghĩa của mitigate');
  });

  it('không lựa chọn nào trùng đáp án đúng', () => {
    const trap = card(1, 'mitigate', ['nghĩa của mitigate', 'phóng đại', 'trì hoãn']);
    const pool = [trap, card(2, 'resilient'), card(3, 'scrutinise')];

    const q = buildQuestion(trap, pool, fixedRandom(0));

    const correct = q!.options[q!.correctIndex];
    expect(q!.options.filter((o) => o === correct)).toHaveLength(1);
  });

  it('không có mồi nhử và hàng đợi chỉ có chính nó thì trả null', () => {
    const lonely = card(1, 'mitigate');

    expect(buildQuestion(lonely, [lonely], fixedRandom(0))).toBeNull();
  });

  it('chỉ bù được 1 mồi nhử thì vẫn dựng được câu 2 lựa chọn', () => {
    const bare = card(1, 'mitigate');
    const pool = [bare, card(2, 'resilient')];

    const q = buildQuestion(bare, pool, fixedRandom(0));

    expect(q!.options).toHaveLength(2);
    expect(q!.options[q!.correctIndex]).toBe('nghĩa của mitigate');
  });

  it('correctIndex luôn trỏ đúng vào đáp án đúng dù trộn kiểu gì', () => {
    for (const r of [0, 0.25, 0.5, 0.75, 0.99]) {
      const q = buildQuestion(FULL, [], fixedRandom(r));
      const expected = q!.direction === 'EN_VI' ? 'nghĩa của mitigate' : 'mitigate';
      expect(q!.options[q!.correctIndex]).toBe(expected);
    }
  });
});
```

- [ ] **Step 3: Chạy test để xác nhận nó đỏ**

```bash
cd extension && npm test -- src/shared/mcq.test.ts
```

Kỳ vọng: FAIL — không import được `./mcq`.

- [ ] **Step 4: Viết `shared/mcq.ts`**

Tạo `extension/src/shared/mcq.ts`:

```ts
import type { CardDto, Rating } from './types';

export type QuizDirection = 'EN_VI' | 'VI_EN';

export interface Question {
  direction: QuizDirection;
  card: CardDto;
  /** Đã trộn sẵn. Độ dài 2 tới 4 tuỳ số mồi nhử gom được. */
  options: string[];
  correctIndex: number;
}

const MAX_DISTRACTORS = 3;
const MIN_OPTIONS = 2;

const EASY_UNDER_MS = 5_000;
const GOOD_UNDER_MS = 15_000;
/** Trên mốc này coi như người dùng rời máy, bỏ tín hiệu thời gian đi. */
const AWAY_OVER_MS = 60_000;

/**
 * Suy ra mức SM-2 từ kết quả và thời gian trả lời.
 *
 * <p>Dùng đủ bốn mức là có chủ ý: nếu chỉ có GOOD/AGAIN thì ΔEF chỉ có thể là 0 hoặc
 * −0.32, mọi thẻ sẽ tụt dần về sàn 1.3 và khoảng cách ôn teo lại vĩnh viễn.
 */
export function ratingFor(correct: boolean, elapsedMs: number): Rating {
  if (!correct) return 'AGAIN';
  if (elapsedMs < EASY_UNDER_MS) return 'EASY';
  if (elapsedMs < GOOD_UNDER_MS) return 'GOOD';
  if (elapsedMs > AWAY_OVER_MS) return 'GOOD';
  return 'HARD';
}

/**
 * Dựng một câu trắc nghiệm cho thẻ. Trả null khi không gom nổi tối thiểu 2 lựa chọn —
 * gọi bên ngoài phải bỏ qua thẻ đó chứ không được coi là đã ôn.
 *
 * @param pool hàng đợi đang nạp trong panel, dùng để bù mồi nhử khi thẻ chưa có bộ riêng
 * @param random tiêm vào để test tất định
 */
export function buildQuestion(
  card: CardDto,
  pool: CardDto[],
  random: () => number,
): Question | null {
  const direction: QuizDirection = random() < 0.5 ? 'EN_VI' : 'VI_EN';
  const correct = direction === 'EN_VI' ? card.meaningVi : card.term;

  const own = direction === 'EN_VI' ? card.viDistractors : card.enDistractors;
  const fallback = pool
    .filter((other) => other.id !== card.id)
    .map((other) => (direction === 'EN_VI' ? other.meaningVi : other.term));

  const distractors = pickDistinct([...own, ...fallback], correct, MAX_DISTRACTORS);
  if (distractors.length + 1 < MIN_OPTIONS) {
    return null;
  }

  const options = shuffle([correct, ...distractors], random);
  return { direction, card, options, correctIndex: options.indexOf(correct) };
}

/** Lấy tối đa `max` phần tử khác rỗng, khác nhau, và khác đáp án đúng. */
function pickDistinct(candidates: string[], correct: string, max: number): string[] {
  const seen = new Set<string>([key(correct)]);
  const picked: string[] = [];
  for (const candidate of candidates) {
    if (picked.length >= max) break;
    if (!candidate || !candidate.trim()) continue;
    const k = key(candidate);
    if (seen.has(k)) continue;
    seen.add(k);
    picked.push(candidate);
  }
  return picked;
}

function key(value: string): string {
  return value.trim().toLowerCase();
}

/** Fisher-Yates với nguồn ngẫu nhiên tiêm từ ngoài. */
function shuffle(items: string[], random: () => number): string[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}
```

- [ ] **Step 5: Chạy test để xác nhận nó xanh**

```bash
cd extension && npm test -- src/shared/mcq.test.ts
```

Kỳ vọng: PASS, 12 test.

- [ ] **Step 6: Chạy type check**

```bash
cd extension && npm run build
```

Kỳ vọng: xanh. Sẽ **đỏ** ở `ReviewTab.test.tsx` nếu helper `card()` trong file đó chưa có
hai field mới — đó là việc của Task 6. Nếu đỏ đúng ở chỗ đó thì sang Step 7; đỏ ở chỗ khác
thì sửa trước khi commit.

- [ ] **Step 7: Commit**

```bash
git add extension/src/shared/mcq.ts extension/src/shared/mcq.test.ts extension/src/shared/types.ts
git commit -m "feat(ext): module thuần dựng câu trắc nghiệm và suy ra rating"
```

---

### Task 6: `ReviewTab` dạng trắc nghiệm

**Files:**
- Modify: `extension/src/sidepanel/ReviewTab.tsx` (viết lại toàn bộ)
- Modify: `extension/src/sidepanel/ReviewTab.test.tsx` (viết lại toàn bộ)
- Modify: `extension/src/sidepanel/styles.css:345-361`

**Interfaces:**
- Consumes: `buildQuestion`, `ratingFor`, `Question` (Task 5); `sendToBackground`, `loadSettings`, `speak` đã có.
- Produces: không có interface mới — đây là lớp vỏ hiển thị.

- [ ] **Step 1: Viết test thất bại**

Thay toàn bộ `extension/src/sidepanel/ReviewTab.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReviewTab } from './ReviewTab';
import type { CardDto } from '../shared/types';

function card(id: number, term: string): CardDto {
  return {
    id, vocabEntryId: id * 10, term, ipa: '/test/', pos: 'verb',
    meaningVi: `nghĩa của ${term}`, definitionEn: null, cefr: null, bandLevel: null,
    collocations: [], examples: [], state: 'NEW', dueDate: '2026-08-06',
    // Mồi nhử cố ý KHÔNG chứa term làm chuỗi con — nếu chứa thì phép so chuỗi trong
    // test sẽ dính nhầm mồi nhử và test "chọn đúng" trở nên vô nghĩa.
    viDistractors: [`sai một ${id}`, `sai hai ${id}`, `sai ba ${id}`],
    enDistractors: [`alpha${id}`, `beta${id}`, `gamma${id}`],
  };
}

/** Nút lựa chọn hiện dạng "3. nội dung" — cắt số thứ tự để so đúng nội dung. */
function optionText(button: HTMLElement): string {
  return (button.textContent ?? '').replace(/^\d+\.\s*/, '');
}

/** Đáp án đúng là meaningVi (chiều EN → VI) hoặc term (chiều VI → EN), tuỳ lượt bốc. */
function isCorrectFor(term: string, button: HTMLElement): boolean {
  const text = optionText(button);
  return text === `nghĩa của ${term}` || text === term;
}

const OK_REVIEW = {
  ok: true, data: { nextDueDate: '2026-08-07', intervalDays: 1, easeFactor: 2.5 },
};

/** Giả lập service worker: hàng đợi cho GET_DUE_CARDS, kết quả chấm cho SUBMIT_REVIEW. */
function mockQueue(cards: CardDto[] | { ok: false; error: unknown }, review: unknown = OK_REVIEW) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) => {
      if (request.type === 'GET_DUE_CARDS') {
        return Array.isArray(cards) ? { ok: true, data: cards } : cards;
      }
      if (request.type === 'SUBMIT_REVIEW') return review;
      return { ok: true, data: null };
    },
  );
}

function submittedReviews() {
  return (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mock.calls
    .map((call) => call[0])
    .filter((request: { type: string }) => request.type === 'SUBMIT_REVIEW');
}

describe('ReviewTab', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await chrome.storage.local.clear();
  });

  it('hiện bốn lựa chọn và không lộ đáp án ở chỗ nào khác', async () => {
    mockQueue([card(1, 'mitigate')]);

    render(<ReviewTab />);

    const options = await screen.findAllByRole('button', { name: /^\d\./ });
    expect(options).toHaveLength(4);
  });

  it('chiều VI → EN không lộ term và không có nút phát âm', async () => {
    // random cố định 0.99 đẩy buildQuestion sang chiều VI_EN.
    // Khôi phục thủ công ở cuối test: vi.clearAllMocks() KHÔNG gỡ spy, để rò rỉ thì mọi
    // test sau đều bị ép sang một chiều duy nhất.
    const randomSpy = vi.spyOn(Math, 'random').mockReturnValue(0.99);
    mockQueue([card(1, 'mitigate')]);

    render(<ReviewTab />);
    await screen.findAllByRole('button', { name: /^\d\./ });

    expect(screen.getByText('nghĩa của mitigate')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /phát âm/i })).not.toBeInTheDocument();

    randomSpy.mockRestore();
  });

  it('chọn đúng thật nhanh thì gửi SUBMIT_REVIEW mức EASY', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d\./ });
    const correct = options.find((b) => isCorrectFor('mitigate', b))!;
    await userEvent.click(correct);

    expect(submittedReviews()).toHaveLength(1);
    expect(submittedReviews()[0]).toMatchObject({ cardId: 1, rating: 'EASY' });
  });

  it('chọn sai thì gửi mức AGAIN', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d\./ });
    const wrong = options.find((b) => !isCorrectFor('mitigate', b))!;
    await userEvent.click(wrong);

    expect(submittedReviews()[0]).toMatchObject({ cardId: 1, rating: 'AGAIN' });
  });

  it('một thẻ chỉ gửi đúng một SUBMIT_REVIEW dù bấm thêm lựa chọn khác', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d\./ });
    await userEvent.click(options[0]);
    await userEvent.click(options[1]);
    await userEvent.click(options[2]);

    expect(submittedReviews()).toHaveLength(1);
  });

  it('chọn xong mới hiện phần chi tiết và nút Tiếp', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    expect(screen.queryByRole('button', { name: /tiếp/i })).not.toBeInTheDocument();

    const options = await screen.findAllByRole('button', { name: /^\d\./ });
    await userEvent.click(options[0]);

    expect(screen.getByRole('button', { name: /tiếp/i })).toBeInTheDocument();
  });

  it('bấm Tiếp thì sang thẻ sau', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d\./ });
    await userEvent.click(options[0]);
    await userEvent.click(screen.getByRole('button', { name: /tiếp/i }));

    expect(await screen.findByText('2/2')).toBeInTheDocument();
  });

  it('SUBMIT_REVIEW lỗi thì giữ nguyên thẻ và có nút Thử lại', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')],
      { ok: false, error: { code: 'INTERNAL', message: 'Backend chết', retryable: true } });

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d\./ });
    await userEvent.click(options[0]);

    expect(await screen.findByText(/backend chết/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /thử lại/i })).toBeInTheDocument();
    expect(screen.getByText('1/2')).toBeInTheDocument();
    // Chưa chấm được thì không cho đi tiếp, bỏ qua lúc này là mất luôn lượt chấm
    expect(screen.queryByRole('button', { name: /^tiếp$/i })).not.toBeInTheDocument();
  });

  it('hàng đợi rỗng hiện empty state', async () => {
    mockQueue([]);

    render(<ReviewTab />);

    expect(await screen.findByText(/không còn thẻ nào đến hạn/i)).toBeInTheDocument();
  });

  it('thẻ không dựng được câu hỏi thì bị bỏ qua và KHÔNG gửi SUBMIT_REVIEW', async () => {
    const bare: CardDto = { ...card(1, 'mitigate'), viDistractors: [], enDistractors: [] };
    mockQueue([bare]);

    render(<ReviewTab />);

    expect(await screen.findByText(/chưa tạo được câu hỏi/i)).toBeInTheDocument();
    expect(submittedReviews()).toHaveLength(0);
  });

  it('nạp hàng đợi theo đúng hạn mức từ mới trong cài đặt', async () => {
    mockQueue([card(1, 'mitigate')]);
    await chrome.storage.local.set({ settings: { newWordsPerDay: 7 } });

    render(<ReviewTab />);
    await screen.findAllByRole('button', { name: /^\d\./ });

    expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'GET_DUE_CARDS', newLimit: 7 }),
    );
  });
});
```

> Test "chọn đúng thật nhanh → EASY" dựa vào việc `userEvent.click` xảy ra trong vài chục
> mili giây thực tế, dưới ngưỡng 5s — không cần fake timer. Nếu máy chạy test chậm bất
> thường làm test này chập chờn thì mới bọc `vi.useFakeTimers()`.

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd extension && npm test -- src/sidepanel/ReviewTab.test.tsx
```

Kỳ vọng: FAIL — `ReviewTab` vẫn đang là thẻ lật, không có nút lựa chọn nào tên `1.`…

- [ ] **Step 3: Viết lại `ReviewTab.tsx`**

Thay toàn bộ `extension/src/sidepanel/ReviewTab.tsx`:

```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import { loadSettings } from '../shared/settings';
import { speak } from '../shared/speech';
import { buildQuestion, ratingFor, type Question } from '../shared/mcq';
import type { ApiError, CardDto, Rating } from '../shared/types';

const QUEUE_LIMIT = 50;

export function ReviewTab() {
  const [queue, setQueue] = useState<CardDto[]>([]);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  // Mức vừa chấm, để nút Thử lại gửi lại ĐÚNG mức đó chứ không đoán bừa.
  const [lastRating, setLastRating] = useState<Rating | null>(null);
  // Mốc bắt đầu tính giờ, đặt lại mỗi khi câu hỏi đổi.
  const startedAt = useRef(Date.now());
  const container = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const { newWordsPerDay } = await loadSettings();
    const response = await sendToBackground({
      type: 'GET_DUE_CARDS', limit: QUEUE_LIMIT, newLimit: newWordsPerDay,
    });
    if (response.ok) {
      setQueue(response.data);
      setIndex(0);
      setPicked(null);
      setError(null);
    } else {
      setError(response.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  // Dựng câu hỏi một lần cho mỗi thẻ. Thẻ nào không dựng được thì để null và bị bỏ qua —
  // chưa ôn thì không được đổi lịch, nên cũng không gửi SUBMIT_REVIEW.
  const questions = useMemo(
    () => queue.map((card) => buildQuestion(card, queue, Math.random)),
    [queue],
  );
  const playable = useMemo(
    () => questions.filter((q): q is Question => q !== null),
    [questions],
  );
  const question = playable[index];

  useEffect(() => { startedAt.current = Date.now(); }, [index]);

  // Phím tắt chỉ chạy khi div đang giữ focus. Bấm chuột vào một lựa chọn đẩy focus sang
  // nút đó, mà nút bị khoá ngay sau đấy nên focus rơi về body — phải kéo focus về đây,
  // nếu không phím Enter để sang thẻ sau sẽ không ăn.
  useEffect(() => { container.current?.focus(); }, [index, picked]);

  async function submit(rating: Rating, cardId: number) {
    setLastRating(rating);
    setSubmitting(true);
    const response = await sendToBackground({ type: 'SUBMIT_REVIEW', cardId, rating });
    setSubmitting(false);
    setError(response.ok ? null : response.error);
  }

  async function choose(optionIndex: number) {
    if (!question || picked !== null || submitting) return;

    setPicked(optionIndex);
    const correct = optionIndex === question.correctIndex;
    await submit(ratingFor(correct, Date.now() - startedAt.current), question.card.id);
  }

  function next() {
    setPicked(null);
    setError(null);
    setIndex((i) => i + 1);
  }

  async function speakTerm() {
    if (!question) return;
    const { voiceName } = await loadSettings();
    speak(question.card.term, voiceName);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!question) return;
    if (picked === null) {
      const n = Number(event.key);
      if (Number.isInteger(n) && n >= 1 && n <= question.options.length) {
        void choose(n - 1);
      }
      return;
    }
    if (event.key === 'Enter') next();
  }

  if (loading) return <p className="status">Đang tải…</p>;

  if (error && !question) {
    return (
      <div className="empty">
        <p>{error.message}</p>
        {error.retryable && <button type="button" onClick={() => void load()}>Thử lại</button>}
      </div>
    );
  }

  if (!question) {
    const blocked = queue.length > 0 && playable.length === 0;
    return (
      <div className="empty">
        <p>
          {blocked
            ? 'Chưa tạo được câu hỏi — mồi nhử đang được sinh, thử lại sau ít phút.'
            : 'Hôm nay không còn thẻ nào đến hạn.'}
        </p>
        <button type="button" onClick={() => void load()}>Tải lại</button>
      </div>
    );
  }

  const card = question.card;

  return (
    // tabIndex để div nhận được phím tắt mà không cần bắt sự kiện toàn cục
    <div className="review-tab" ref={container} tabIndex={-1} onKeyDown={onKeyDown}>
      <p className="status">{index + 1}/{playable.length}</p>

      {error && lastRating && (
        <p className="status bad" role="alert">
          {error.message}{' '}
          {error.retryable && (
            <button
              type="button"
              disabled={submitting}
              onClick={() => void submit(lastRating, card.id)}
            >
              Thử lại
            </button>
          )}
        </p>
      )}

      <div className="review-card">
        <div className="review-front">
          {question.direction === 'EN_VI' ? (
            <>
              <strong>{card.term}</strong>
              {card.ipa && <span className="meta">{card.ipa}</span>}
              <button
                type="button"
                aria-label={`Phát âm ${card.term}`}
                onClick={() => void speakTerm()}
              >
                🔊
              </button>
            </>
          ) : (
            <strong>{card.meaningVi}</strong>
          )}
        </div>
      </div>

      <div className="review-options">
        {question.options.map((option, i) => (
          <button
            key={option}
            type="button"
            disabled={picked !== null}
            className={optionClass(i, picked, question.correctIndex)}
            onClick={() => void choose(i)}
          >
            {i + 1}. {option}
          </button>
        ))}
      </div>

      {picked !== null && (
        <>
          <div className="review-back">
            <p className="vi">{card.term} — {card.meaningVi}</p>
            {card.pos && <span className="meta">{card.pos}</span>}
            {card.cefr && <span className="meta">{card.cefr}</span>}
            {card.bandLevel && (
              <span className="band" title="Band do AI ước lượng, chỉ mang tính tham khảo">
                {card.bandLevel}
              </span>
            )}
            {card.definitionEn && <p className="review-definition">{card.definitionEn}</p>}
          </div>
          {/* Lỗi chưa xử lý xong thì KHÔNG cho đi tiếp — bỏ qua lúc này là mất luôn lượt chấm. */}
          {!error && (
            <button type="button" className="review-next" onClick={next}>Tiếp</button>
          )}
        </>
      )}
    </div>
  );
}

/** Chỉ tô màu sau khi đã chọn: đáp án đúng luôn xanh, ô chọn sai thì đỏ. */
function optionClass(index: number, picked: number | null, correctIndex: number): string {
  if (picked === null) return 'review-option';
  if (index === correctIndex) return 'review-option correct';
  if (index === picked) return 'review-option wrong';
  return 'review-option';
}
```

- [ ] **Step 4: Chạy test để xác nhận nó xanh**

```bash
cd extension && npm test -- src/sidepanel/ReviewTab.test.tsx
```

Kỳ vọng: PASS, 11 test.

- [ ] **Step 5: Thay style bốn nút chấm bằng style lựa chọn**

Trong `extension/src/sidepanel/styles.css`, thay khối `.review-ratings` / `.review-reveal`
(dòng 345–361) bằng:

```css
.review-options { display: grid; gap: 6px; margin-top: 10px; }
.review-option {
  padding: 10px 12px;
  text-align: left;
  font-size: 14px;
  border: 1px solid var(--border-2);
  border-radius: 9px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}
.review-option:hover:not(:disabled) { background: var(--surface-2); }
.review-option:disabled { cursor: default; }
.review-option.correct { border-color: #2e7d52; background: #eaf6ef; color: #17512f; }
.review-option.wrong { border-color: #b3403a; background: #fbeceb; color: #7a2620; }

.review-next {
  width: 100%;
  margin-top: 10px;
  padding: 9px 12px;
  font-weight: 560;
  border: 1px solid var(--border-2);
  border-radius: 9px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}
.review-next:hover { background: var(--surface-2); }
```

> Mở `styles.css` đọc trước khi sửa: dùng đúng tên biến màu (`--border-2`, `--surface`,
> `--text`…) mà file đang dùng. Nếu tên khác thì bám tên thật, đừng bịa biến mới. Hai màu
> đúng/sai cố ý viết literal vì bảng biến hiện tại không có màu ngữ nghĩa nào.

- [ ] **Step 6: Chạy toàn bộ test và type check**

```bash
cd extension && npm test && npm run build
```

Kỳ vọng: cả hai xanh. `noUnusedLocals` sẽ bắt mọi import thừa còn sót từ bản cũ.

- [ ] **Step 7: Commit**

```bash
git add extension/src/sidepanel/ReviewTab.tsx \
        extension/src/sidepanel/ReviewTab.test.tsx \
        extension/src/sidepanel/styles.css
git commit -m "feat(ext): màn ôn tập dạng chọn đáp án, trộn hai chiều"
```

---

### Task 7: Tài liệu và kiểm chứng đầu-cuối

**Files:**
- Modify: `README.md` (mục "Ôn tập")
- Modify: `docs/superpowers/specs/2026-08-06-phase2-3-srs-quiz-design.md:203`

**Interfaces:** không có — task hoàn thiện.

- [ ] **Step 1: Viết lại mục "Ôn tập" trong README**

Thay toàn bộ mục `## Ôn tập` trong `README.md` (bảng bốn nút hiện tại mô tả sai hoàn toàn)
bằng:

```markdown
## Ôn tập

Mỗi từ đơn lưu vào sổ tự động vào lịch ôn (câu dài thì không — flashcard cả câu không có
giá trị ôn tập). Số trên icon extension là số thẻ đến hạn, tự cập nhật mỗi 30 phút và
ngay sau khi bạn ôn hoặc lưu từ mới.

Mở side panel → tab **Ôn tập**. Mỗi thẻ là một câu trắc nghiệm bốn lựa chọn, trộn ngẫu
nhiên hai chiều:

- **Anh → Việt:** hiện từ, IPA và nút phát âm, bạn chọn nghĩa đúng.
- **Việt → Anh:** hiện nghĩa tiếng Việt, bạn chọn từ đúng.

Bấm phím `1`–`4` hoặc bấm chuột để chọn. Chọn xong hiện ngay đáp án đúng cùng phần chi
tiết (từ loại, CEFR, band, định nghĩa tiếng Anh); bấm **Tiếp** hoặc `Enter` sang thẻ sau.

Khoảng cách ôn lần sau suy ra từ kết quả và thời gian bạn trả lời:

| Kết quả | Ảnh hưởng |
|---|---|
| Sai | về 1 ngày, EF −0.32, đếm một lần quên |
| Đúng, dưới 5 giây | như "nhớ ngay": 1 ngày → 6 ngày → × EF, rồi × 1.3, EF +0.10 |
| Đúng, 5–15 giây | 1 ngày → 6 ngày → × EF |
| Đúng, 15–60 giây | khoảng cách × 1.2, EF −0.14 |
| Đúng, trên 60 giây | tính như 5–15 giây — quá lâu thì coi như bạn rời máy, không phạt |

Ba đáp án sai do AI sinh sẵn cho từng từ và lưu lại, nên chỉ tốn một lượt gọi Gemini cho
mỗi từ. Từ mới lưu có thể chưa kịp có bộ đáp án sai riêng; lúc đó bài ôn tạm mượn nghĩa
của các từ khác trong hàng đợi, và bộ thật sẽ có ở lần ôn sau.

Số từ **mới** mỗi ngày mặc định giới hạn 30, đổi trong Options. Thẻ đã đến hạn không bị
giới hạn — đến hạn bao nhiêu hiện bấy nhiêu.
```

- [ ] **Step 2: Ghi chú vào spec Phase 2/3**

Trong `docs/superpowers/specs/2026-08-06-phase2-3-srs-quiz-design.md`, chèn ngay dưới
dòng tiêu đề `### 2.9 Màn ôn tập`:

```markdown
> **Đã bị ghi đè.** Màn ôn tập nay là trắc nghiệm bốn lựa chọn trộn hai chiều, rating suy
> ra tự động — xem [design 2026-08-06 màn ôn tập chọn đáp án](2026-08-06-srs-mcq-review-design.md).
> Phần mô tả thẻ lật bên dưới giữ lại để tra cứu lịch sử.
```

- [ ] **Step 3: Chạy toàn bộ kiểm chứng tự động**

```bash
cd backend && mvn test
cd ../extension && npm test && npm run build
```

Kỳ vọng: cả ba xanh. Dán output thật vào báo cáo — không nói "đã xong" khi chưa có output.

- [ ] **Step 4: Kiểm chứng ranh giới module**

```bash
grep -r "ieltstranslator.srs" backend/src/main/java/com/hiepnn/ieltstranslator/vocabulary/
```

Kỳ vọng: **rỗng**.

- [ ] **Step 5: Kiểm chứng thủ công đầu-cuối**

Backend đang chạy phải được khởi động lại thì Flyway mới chạy `V4` và mới có route mang
mồi nhử. Nếu đang chạy từ IDE thì restart run config "Backend local"; nếu chạy Docker:

```bash
docker compose up -d --build
curl http://127.0.0.1:8080/api/health
curl 'http://127.0.0.1:8080/api/srs/due?limit=5&newLimit=30'
```

Kỳ vọng: mỗi phần tử có `viDistractors` và `enDistractors`. Lần gọi đầu chúng rỗng (mồi
nhử vừa được xếp hàng sinh); gọi lại sau ~10 giây thì đã có đủ ba phần tử mỗi mảng.

Rồi trong Chrome:
1. Tải lại extension unpacked từ `extension/dist/`.
2. Bôi đen một từ tiếng Anh mới trên trang bất kỳ → bubble hiện → bấm lưu.
3. Mở side panel → tab **Ôn tập** → thấy câu trắc nghiệm, đủ bốn lựa chọn.
4. Bấm phím `1` → đáp án đúng tô xanh, phần chi tiết mở ra, nút **Tiếp** hiện.
5. Kiểm tra badge giảm đi 1.
6. Tải lại tab vài lần → thấy có lượt hỏi chiều Anh → Việt, có lượt chiều Việt → Anh.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/superpowers/specs/2026-08-06-phase2-3-srs-quiz-design.md
git commit -m "docs: mục ôn tập trắc nghiệm, ghi chú ghi đè mục 2.9"
```

---

## Kiểm chứng cuối

Xong khi tất cả những điều sau đúng, có output thật chứng minh:

- [ ] `cd backend && mvn test` xanh toàn bộ
- [ ] `cd extension && npm test` xanh toàn bộ
- [ ] `cd extension && npm run build` xanh (type check)
- [ ] `grep -r "ieltstranslator.srs" backend/src/main/java/com/hiepnn/ieltstranslator/vocabulary/` **rỗng**
- [ ] Lưu một từ đơn mới → sau ít giây, `/api/srs/due` trả thẻ đó với đủ 3 mồi nhử mỗi chiều
- [ ] Lưu một câu → không có bản ghi `srs_distractor` nào được tạo
- [ ] Gemini chết (đổi `GEMINI_API_KEY` sai rồi lưu một từ) → từ vẫn vào sổ, tab Ôn tập vẫn ôn được bằng mồi nhử mượn
- [ ] Chọn đáp án đúng thật nhanh → thẻ giãn ra rõ rệt; chọn sai → thẻ về 1 ngày
- [ ] Xoá một từ trong tab Sổ từ → không còn `srs_distractor` tương ứng, backend không lỗi
