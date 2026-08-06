# IELTS Translator — Phase 2 (SRS) + Phase 3 (Quiz)

**Ngày:** 2026-08-06
**Trạng thái:** Design đã duyệt
**Tiền đề:** [design gốc 2026-08-03](2026-08-03-ielts-translator-extension-design.md) · Phase 1 đã xong (dịch hai chiều, cache, bubble, sổ từ)

Tài liệu này chi tiết hoá mục 8 và mục 9 của design gốc, và **ghi đè** design gốc ở những chỗ nêu rõ trong mục "Sai lệch so với design gốc".

---

## 1. Phạm vi

**Phase 2** — SM-2, màn ôn tập, badge số từ đến hạn. Kết thúc phase là ôn tập dùng được thật, không chờ Phase 3.

**Phase 3** — ba loại quiz, chấm bài, trong đó `FREE_WRITE` chấm bằng Gemini.

Hai phase dùng chung một spec (tài liệu này) nhưng **hai plan thực thi tách rời**, chạy tuần tự. Phase 2 ship trước.

**Ngoài phạm vi:** learning steps trong ngày kiểu Anki, đồng bộ đám mây, thống kê/biểu đồ tiến độ, quiz tác động tới lịch SRS.

---

## 2. Phase 2 — SRS

### 2.1 Module `srs`

```
srs/SrsScheduler.java        công thức SM-2 — hàm thuần, không Spring, không DB
srs/CardState.java           NEW | REVIEW | RELEARNING
srs/Rating.java              AGAIN(0) HARD(1) GOOD(2) EASY(3)
srs/SrsCard.java             SrsCardRepository.java
srs/ReviewLog.java           ReviewLogRepository.java
srs/SrsCardCreator.java      listener tạo card khi lưu từ mới
srs/SrsService.java          SrsController.java
srs/dto/CardDto.java  dto/ReviewRequest.java  dto/ReviewResponse.java  dto/SrsStatsDto.java
```

Chiều phụ thuộc: `srs → vocabulary`. `vocabulary` không được import gì từ `srs`.

### 2.2 `SrsScheduler` — hàm thuần

Chữ ký:

```java
record Schedule(int intervalDays, double easeFactor, int repetitions,
                int lapses, LocalDate dueDate, CardState state) {}

Schedule next(SrsCard card, Rating rating, LocalDate today)
```

Không đọc DB, không đọc đồng hồ hệ thống — `today` truyền vào. Đây là điều kiện để test bằng bảng thuần tuý.

**Design gốc mục 8 tự mâu thuẫn ở chỗ EF.** Dòng `AGAIN` ghi `EF -= 0.2`, nhưng công thức `EF'` bên dưới tại `q = 0` cho ra `−0.32`, không phải `−0.2`:

| Rating | q | ΔEF theo công thức |
|---|---|---|
| `AGAIN` | 0 | −0.32 |
| `HARD` | 1 | −0.14 |
| `GOOD` | 2 | 0.00 |
| `EASY` | 3 | +0.10 |

**Chốt: dùng đúng một công thức `EF'` cho cả bốn rating**, bỏ dòng `EF -= 0.2`. Một nguồn sự thật duy nhất, và `−0.32` là SM-2 chuẩn. Hệ quả: bấm `AGAIN` chạm sàn 1.3 nhanh hơn so với cách hiểu `−0.2`.

```
AGAIN → repetitions = 0, interval = 1, lapses++, state = RELEARNING
HARD  → interval = round(interval × 1.2)
GOOD  → repetitions 1 → 1 ngày | repetitions 2 → 6 ngày | repetitions ≥ 3 → round(interval × EF)
EASY  → như GOOD, rồi × 1.3

EF' = max(1.3, EF + (0.1 − (3−q)·(0.08 + (3−q)·0.02)))   q: AGAIN=0, HARD=1, GOOD=2, EASY=3
dueDate = today + intervalDays
```

EF dùng để tính interval là **EF sau khi cập nhật**, không phải EF cũ.

Chi tiết chốt thêm (design gốc không nói, cần thiết để test xác định):

- `intervalDays` tối thiểu là **1** sau mọi phép nhân — làm tròn nửa lên (`Math.round`).
- `repetitions` tăng 1 với `HARD`, `GOOD`, `EASY`; đặt về 0 với `AGAIN`.
- Sau `AGAIN`, state = `RELEARNING`. Lần review kế tiếp bất kỳ rating nào khác `AGAIN` đưa state về `REVIEW`.
- Card `NEW` sau lượt review đầu tiên chuyển sang `REVIEW` (hoặc `RELEARNING` nếu bấm `AGAIN`).

### 2.3 Card được tạo lúc nào

`VocabService.save()` phát `VocabEntrySavedEvent(entryId, pos)` qua `ApplicationEventPublisher` **chỉ khi** tạo entry mới (`alreadyExists == false`). `SrsCardCreator` trong module `srs` bắt bằng `@EventListener`, chạy đồng bộ trong cùng transaction, và tạo card khi `pos != "phrase"`.

Card mới: `ease_factor = 2.5`, `interval_days = 0`, `repetitions = 0`, `lapses = 0`, `due_date = hôm nay`, `state = NEW`.

Lý do dùng event thay vì gọi thẳng: giữ chiều phụ thuộc `srs → vocabulary`, để `vocabulary` vẫn test độc lập được.

**Câu (`pos = 'phrase'`) không vào lịch ôn.** Flashcard một câu dài không có giá trị ôn tập; câu vẫn nằm trong sổ từ và vẫn tra lại được.

### 2.4 Migration `V3__srs.sql`

```sql
CREATE TABLE srs_card (
    id              BIGSERIAL   PRIMARY KEY,
    vocab_entry_id  BIGINT      NOT NULL UNIQUE
                    REFERENCES vocab_entry(id) ON DELETE CASCADE,
    ease_factor     DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    interval_days   INT         NOT NULL DEFAULT 0,
    repetitions     INT         NOT NULL DEFAULT 0,
    lapses          INT         NOT NULL DEFAULT 0,
    due_date        DATE        NOT NULL,
    state           VARCHAR(16) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_srs_due ON srs_card (due_date, state);

CREATE TABLE review_log (
    id            BIGSERIAL   PRIMARY KEY,
    card_id       BIGINT      NOT NULL REFERENCES srs_card(id) ON DELETE CASCADE,
    rating        VARCHAR(8)  NOT NULL,
    reviewed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_interval INT         NOT NULL,
    new_interval  INT         NOT NULL
);

CREATE INDEX idx_review_log_reviewed_at ON review_log (reviewed_at);

-- Backfill: mọi từ đơn đã lưu ở Phase 1 vào lịch ôn ngay
INSERT INTO srs_card (vocab_entry_id, due_date, state)
SELECT id, CURRENT_DATE, 'NEW' FROM vocab_entry WHERE pos <> 'phrase';
```

`ON DELETE CASCADE` là bắt buộc: `DELETE /api/vocab/{id}` đã tồn tại từ Phase 1: thiếu cascade là hỏng ngay lần xoá đầu tiên.

`UNIQUE` trên `vocab_entry_id` khẳng định quyết định "một thẻ mỗi từ" ở tầng schema.

### 2.5 Hàng đợi ôn và giới hạn từ mới

```
GET /api/srs/due?limit=50&newLimit=30
```

Hàng đợi ghép hai phần:

1. **Card đến hạn** — `state != 'NEW' AND due_date <= today`. **Không giới hạn** (design gốc: "card đến hạn không bị giới hạn").
2. **Card mới** — `state = 'NEW'`, tối đa `newLimit − đã_học_hôm_nay`, sắp theo `created_at` tăng dần (từ lưu trước học trước).

Tổng số phần tử trả về cắt ở `limit` (mặc định 50), card đến hạn ưu tiên trước card mới.

**`đã_học_hôm_nay`** suy ra từ `review_log`, không cần bảng đếm:

```sql
SELECT count(*) FROM review_log
WHERE reviewed_at >= CURRENT_DATE AND prev_interval = 0
```

Lượt review đầu đời của một card là lượt duy nhất có `prev_interval = 0`: card mới có `interval_days = 0`, còn `AGAIN` luôn đặt interval về 1 nên mọi lượt sau đó đều có `prev_interval >= 1`.

`newLimit` do extension truyền lên từ Options. Backend không giữ cấu hình này.

### 2.6 API Phase 2

```
GET  /api/srs/due?limit=50&newLimit=30  → [CardDto]
GET  /api/srs/stats                     → { dueCount, newCount, learnedCount }
POST /api/srs/review { cardId, rating } → { nextDueDate, intervalDays, easeFactor }
```

`CardDto` gộp sẵn dữ liệu vocab để panel chỉ gọi một lượt:

```
id, vocabEntryId, term, ipa, pos, meaningVi, definitionEn,
cefr, bandLevel, collocations, examples, state, dueDate
```

`SrsStatsDto`:
- `dueCount` — số card `state != 'NEW' AND due_date <= today`, cộng số card `NEW` còn được phép học hôm nay. Đây là con số hiện trên badge, nên phải khớp đúng độ dài hàng đợi người dùng sẽ thấy.
- `newCount` — tổng số card `state = 'NEW'` (không trừ giới hạn ngày).
- `learnedCount` — số card `repetitions >= 1`.

`POST /api/srs/review` với `cardId` không tồn tại → `NOT_FOUND`. Mỗi lượt ghi một dòng `review_log` với `prev_interval` = interval trước khi tính, `new_interval` = sau khi tính.

### 2.7 Extension Phase 2

| Chỗ sửa | Nội dung |
|---|---|
| `manifest.config.ts` | thêm permission `alarms` |
| `shared/settings.ts` | thêm `newWordsPerDay: number`, mặc định 30, chuẩn hoá về khoảng 0–200 |
| `shared/types.ts` | `CardDto`, `Rating`, `ReviewResponse`, `SrsStats` |
| `shared/messages.ts` | `GET_DUE_CARDS`, `SUBMIT_REVIEW`, `GET_SRS_STATS` vào union `ExtensionRequest` **và** `ResponseMap` |
| `background/api-client.ts` | `getDueCards`, `submitReview`, `srsStats` |
| `background/service-worker.ts` | badge + alarm (mục 2.8) |
| `sidepanel/App.tsx` | tab thứ 3 "Ôn tập" |
| `sidepanel/ReviewTab.tsx` | màn ôn tập |
| `sidepanel/styles.css` | style thẻ và hàng nút rating |
| `options/Options.tsx` | ô nhập "Từ mới mỗi ngày" |
| `README.md` | mục hướng dẫn ôn tập |

### 2.8 Badge

Service worker đăng ký `chrome.alarms.create('srs-badge', { periodInMinutes: 30 })`. Trên `onAlarm`, `onStartup`, `onInstalled`, và sau mỗi `SUBMIT_REVIEW` / `SAVE_WORD` thành công: gọi `/api/srs/stats`, rồi

```
chrome.action.setBadgeText({ text: dueCount > 0 ? String(dueCount) : '' })
```

Backend chết → nuốt lỗi, **xoá badge**, không hiện số cũ đã lỗi thời và không spam log.

### 2.9 Màn ôn tập

Một thẻ mỗi lượt, chiều **EN → VI**.

- **Mặt trước:** `term`, `ipa`, nút phát âm (Web Speech API, giọng theo `settings.voiceName`).
- **Mặt sau:** `meaningVi`, `definitionEn`, `pos`, `cefr`, `bandLevel`, `collocations`, `examples`.
- Nút "Hiện đáp án" lật thẻ. Lật rồi mới hiện bốn nút `Lại · Khó · Tốt · Dễ`.
- Hiện tiến độ dạng `3/12`.

Panel **nạp cả xấp card một lần** rồi ôn trong bộ nhớ; mỗi lần bấm rating gửi một `SUBMIT_REVIEW` và chuyển thẻ ngay, không refetch hàng đợi.

Nút rating bị vô hiệu hoá trong lúc `SUBMIT_REVIEW` đang bay, tránh bấm hai lần ghi hai `review_log`.

`SUBMIT_REVIEW` lỗi → hiện lỗi kèm nút Thử lại, **giữ nguyên thẻ hiện tại**, không nhảy sang thẻ sau.

Trạng thái rỗng: "Hôm nay không còn thẻ nào đến hạn." Backend chết: empty state có nút Thử lại, không crash.

### 2.10 Test Phase 2

| Đối tượng | Kiểu | Nội dung |
|---|---|---|
| `SrsSchedulerTest` | unit, không Docker | bảng `rating × state`; ΔEF đúng từng rating (`−0.32 / −0.14 / 0 / +0.10`); sàn EF 1.3 (bấm `AGAIN` nhiều lần không tụt dưới 1.3); `repetitions` 1 → 1 ngày, 2 → 6 ngày, 3+ → `× EF`; `EASY` `× 1.3`; `HARD` `× 1.2`; interval tối thiểu 1; `lapses` tăng đúng; chuyển state |
| `SrsServiceIT` | Testcontainers | lưu từ đơn tạo card; lưu câu (`pos='phrase'`) **không** tạo card; lưu trùng không tạo card thứ hai; giới hạn từ mới trừ đúng số đã học hôm nay; card đến hạn không bị giới hạn; xoá vocab cascade sạch `srs_card` + `review_log` |
| `SrsControllerIT` | Testcontainers | hình dạng `CardDto` / `SrsStatsDto` / `ReviewResponse`; `cardId` lạ → `NOT_FOUND` |
| Migration `V3` | Testcontainers | backfill tạo card cho từ đơn có sẵn và bỏ qua `pos='phrase'` |
| `ReviewTab.test.tsx` | Vitest + RTL | mặt trước không lộ nghĩa; lật thẻ; bấm rating gửi message đúng; hết bài hiện empty state; lỗi giữ nguyên thẻ và có nút thử lại |
| `settings.test.ts` | Vitest | `newWordsPerDay` mặc định và chuẩn hoá |

---

## 3. Phase 3 — Quiz

### 3.1 Ranh giới `quiz` ↔ `srs`

Design gốc mục 5.1 viết *"`quiz` không biết lịch ôn tồn tại"*, nhưng mục 9 lại yêu cầu chọn ứng viên theo `srs_card.repetitions >= 1`. Truy vấn đó bắt buộc phải đọc `srs_card` — hai câu này không cùng đúng được.

**Chốt lại:** module `quiz` **đọc** `srs_card` (read-only, qua một native query đặt trong `quiz`), và **không bao giờ ghi** vào `srs_card` hay `review_log`. Bất biến đáng giữ là "quiz không tác động tới lịch SRS", và nó kiểm chứng được bằng test (`QuizSrsIsolationIT`).

### 3.2 Module `quiz`

```
quiz/QuizType.java            FILL_BLANK | COLLOCATION_CHOICE | FREE_WRITE
quiz/QuizItem.java            QuizItemRepository.java
quiz/QuizAttempt.java         QuizAttemptRepository.java
quiz/QuizCandidateRepository.java   native query chọn ứng viên
quiz/QuizGenerator.java       gọi Gemini theo lô, dựng item
quiz/QuizItemValidator.java   loại item Gemini trả sai hình dạng
quiz/QuizGrader.java          chấm local — hàm thuần
quiz/QuizService.java         QuizController.java
quiz/dto/…
```

### 3.3 Chọn ứng viên

Khi request có `count` (không có `vocabIds`):

```sql
SELECT v.id
FROM vocab_entry v
JOIN srs_card c ON c.vocab_entry_id = v.id
LEFT JOIN quiz_item qi ON qi.vocab_entry_id = v.id
LEFT JOIN quiz_attempt qa ON qa.quiz_item_id = qi.id
WHERE c.repetitions >= 1
GROUP BY v.id, c.lapses
ORDER BY count(qa.id) ASC, c.lapses DESC, v.id ASC
LIMIT :count
```

Từ chưa ôn lần nào (`repetitions = 0`) **không** được đưa vào quiz — đúng design gốc.

Khi request có `vocabIds`, dùng đúng danh sách đó, bỏ qua điều kiện `repetitions`.

Không có ứng viên nào → trả **mảng rỗng**, không phải lỗi. Panel hiện "Chưa có từ nào đủ điều kiện — cần ôn ít nhất một lượt trước đã." Cách này tránh phải thêm `ErrorCode` mới, vốn bắt buộc động vào switch exhaustive trong `GlobalExceptionHandler`.

### 3.4 Sinh đề

**Gọi Gemini một lượt cho cả lô, mỗi loại một lượt.** 10 từ `FILL_BLANK` là 1 call, không phải 10.

Ba file prompt mới, mỗi file có header `version:` (constraint #5 — sửa nội dung phải tăng version):

| File | Dùng cho |
|---|---|
| `prompts/quiz-fill-blank.md` | sinh N câu chứa từ, che từ đích bằng `___` |
| `prompts/quiz-collocation.md` | sinh 1 đáp án đúng + 3 distractor sai một cách tự nhiên |
| `prompts/quiz-grade-free-write.md` | chấm bài viết |

`FREE_WRITE` **không tốn call sinh đề** — đề bài là chính từ đó, backend tự dựng từ `vocab_entry`.

`PromptLoader` hiện chỉ chọn theo `direction × mode`. Thêm `load(String name)` dùng chung; method cũ trở thành lớp mỏng gọi vào nó.

Schema structured output khi sinh:

```
fill-blank:   { items: [ { term, sentence, answer, hint } ] }     sentence chứa "___"
collocation:  { items: [ { term, question, options[4], correct_index } ] }
```

### 3.5 Tái dùng `quiz_item`

Đây là cách hiện thực "không gọi Gemini mỗi lần mở màn quiz":

1. Lấy các `quiz_item` của những từ đã chọn mà **chưa có `quiz_attempt` nào** và có `prompt_version` khớp version prompt hiện hành.
2. Chỉ gọi Gemini cho phần còn thiếu.

Cột `prompt_version INT` trên `quiz_item` là cách duy nhất làm đề cũ hết hiệu lực khi sửa prompt — cùng nguyên tắc với `lookup_cache`.

Item đã làm rồi **không bị xoá**: `quiz_attempt` là dữ liệu lịch sử, và số lượt làm chính là tiêu chí ưu tiên ở mục 3.3.

### 3.6 Chống output rác

Gemini trả câu thiếu `___`, hoặc `options` có 3 phần tử thay vì 4 — chuyện xảy ra thật dù đã dùng structured output.

`QuizItemValidator` **loại từng item hỏng** rồi lấy tiếp từ phần còn lại, thay vì ném `PARSE_ERROR` giết cả lô. Chỉ khi **không còn item hợp lệ nào** mới ném `PARSE_ERROR`.

Quy tắc hợp lệ:
- `FILL_BLANK`: `sentence` chứa `___`, `answer` không rỗng, `answer` không xuất hiện nguyên văn trong phần còn lại của `sentence`.
- `COLLOCATION_CHOICE`: đúng 4 `options`, không trùng nhau, `0 <= correct_index <= 3`.

### 3.7 Không lộ đáp án

`quiz_item.payload` chứa đáp án, nhưng `QuizItemDto` gửi xuống panel thì **không**:

```
QuizItemDto: id, type, vocabEntryId, term, question, sentence?, options?
```

Người dùng nộp qua `POST /api/quiz/answer`, backend so. `QuizControllerIT` khẳng định response không chứa đáp án.

### 3.8 Migration `V4__quiz.sql`

```sql
CREATE TABLE quiz_item (
    id             BIGSERIAL   PRIMARY KEY,
    vocab_entry_id BIGINT      NOT NULL
                   REFERENCES vocab_entry(id) ON DELETE CASCADE,
    type           VARCHAR(24) NOT NULL,
    payload        JSONB       NOT NULL,
    prompt_version INT         NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_quiz_item_vocab ON quiz_item (vocab_entry_id, type);

CREATE TABLE quiz_attempt (
    id           BIGSERIAL   PRIMARY KEY,
    quiz_item_id BIGINT      NOT NULL REFERENCES quiz_item(id) ON DELETE CASCADE,
    user_answer  TEXT        NOT NULL,
    correct      BOOLEAN     NOT NULL,
    score        INT         NOT NULL,
    ai_feedback  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_quiz_attempt_item ON quiz_attempt (quiz_item_id);
```

`correct BOOLEAN` là bổ sung so với design gốc: `score` một mình không phân biệt được "sai" và "chưa chấm".

### 3.9 API Phase 3

```
POST /api/quiz/generate { vocabIds[]? , count?, types[] } → [QuizItemDto]
POST /api/quiz/answer   { quizItemId, answer }            → { correct, score, feedback, improvedVersion? }
```

`generate` phải có **đúng một** trong `vocabIds` hoặc `count`. Diễn đạt ràng buộc này bằng `@AssertTrue` trên record request, **không** bằng `AppException` — `GlobalExceptionHandler` đã có `handleValidation` bắt `MethodArgumentNotValidException` và trả **HTTP 400** code `INTERNAL`, còn `AppException.of(ErrorCode.INTERNAL, …)` lại rơi vào `statusFor()` và trả **500**. Lỗi request phải là 400.

`types` rỗng → mặc định cả ba loại.

`answer` luôn là **string** trên đường truyền; với `COLLOCATION_CHOICE` backend tự parse thành index. Một hình dạng, không union — string không parse được thành index hợp lệ tính là sai, không phải lỗi.

`quizItemId` không tồn tại → `NOT_FOUND`.

### 3.10 Chấm bài

| Loại | Cách chấm | `score` |
|---|---|---|
| `FILL_BLANK` | Backend: trim, bỏ phân biệt hoa thường, so với đúng dạng đã bị che — **không lemmatize** | 100 / 0 |
| `COLLOCATION_CHOICE` | Backend: so index | 100 / 0 |
| `FREE_WRITE` | Gemini | 0–100 do Gemini trả |

Schema chấm `FREE_WRITE`:

```
{ meaning_ok: bool, grammar_ok: bool, band_ok: bool,
  score: 0-100, feedback_vi: string, improved_version: string }
```

`correct = meaning_ok && grammar_ok`. `band_ok` chỉ đi vào `feedback`, không quyết định đúng/sai — nhãn band là gợi ý tham khảo, không phải sự thật (design gốc mục 6).

Mỗi lần chấm ghi một dòng `quiz_attempt`. Chấm lại cùng một item ghi thêm dòng mới, không ghi đè.

**Quiz không tác động tới lịch SRS.** Chỉ ghi `quiz_attempt`.

### 3.11 Timeout

`GeminiProperties.timeoutSeconds` hiện là **một** giá trị (15s) nướng vào `ClientHttpRequestFactory` trong `GeminiConfig`. Design gốc mục 10 yêu cầu ba mức khác nhau, nên phải tách.

Thêm enum `GeminiTimeout { TRANSLATE, QUIZ_GENERATE, QUIZ_GRADE }` truyền vào `GeminiClient.generateJson`; `GeminiConfig` dựng một `RestClient` cho mỗi mức.

| Biến | Mặc định |
|---|---|
| `GEMINI_TIMEOUT_SECONDS` | 15 |
| `GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS` | 30 |
| `GEMINI_QUIZ_GRADE_TIMEOUT_SECONDS` | 20 |

Cả ba viết dạng `${BIEN:mặc-định}` trong `application.yml` (constraint #6), và thêm vào `.env.example` **và** bảng "Biến môi trường" trong `README.md`.

### 3.12 Timeout phía extension

`ApiClient.request()` hiện gọi `fetch` trần, không có timeout — backend treo là spinner quay mãi. Với sinh quiz (tới 30s phía backend) điều này lộ rõ hơn Phase 1 nhiều.

Thêm tham số `timeoutMs` vào `request()`, dùng `AbortSignal.timeout()`. Mặc định 20s; `generate` 35s; `answer` 25s — mỗi mức nới hơn timeout backend tương ứng để backend kịp trả lỗi có cấu trúc trước khi client tự bỏ cuộc.

Quá hạn → `ApiError` mã `BACKEND_DOWN`, `retryable: true`, thông điệp phân biệt rõ với "không kết nối được".

Đây là **sửa lan sang code Phase 1**: mọi endpoint cũ cũng được bọc timeout.

### 3.13 Extension Phase 3

| Chỗ sửa | Nội dung |
|---|---|
| `shared/types.ts` | `QuizItemDto`, `QuizType`, `AnswerResult` |
| `shared/messages.ts` | `GENERATE_QUIZ`, `ANSWER_QUIZ` |
| `background/api-client.ts` | `generateQuiz`, `answerQuiz` + timeout mục 3.12 |
| `sidepanel/App.tsx` | tab thứ 4 "Quiz" |
| `sidepanel/QuizTab.tsx` | màn quiz |
| `sidepanel/styles.css` | style câu hỏi và lựa chọn |
| `README.md` | mục hướng dẫn quiz |

Luồng màn quiz: chọn số câu (mặc định 10) và tick loại → "Tạo đề" → làm từng câu, nộp từng câu và hiện feedback ngay → hết đề hiện tổng kết `đúng/tổng`.

`FREE_WRITE` chấm mất vài giây: hiện trạng thái đang chấm và khoá nút nộp.

### 3.14 Test Phase 3

| Đối tượng | Kiểu | Nội dung |
|---|---|---|
| `QuizGraderTest` | unit, không Docker | trim và bỏ phân biệt hoa thường; **không** lemmatize (`mitigated` ≠ `mitigate`); so index; answer rác không parse được tính là sai |
| `QuizItemValidatorTest` | unit | loại item thiếu `___`; `options` sai số lượng; `options` trùng nhau; `correct_index` ngoài khoảng; `answer` lộ trong `sentence` |
| `QuizServiceIT` | Testcontainers + WireMock | **đếm số call Gemini** để chứng minh tái dùng item chưa làm; đổi `prompt_version` thì không tái dùng; thứ tự ưu tiên ứng viên; từ `repetitions = 0` bị loại; không có ứng viên → mảng rỗng; lô có item hỏng vẫn trả phần hợp lệ; hỏng hết → `PARSE_ERROR` |
| `QuizSrsIsolationIT` | Testcontainers | làm hết một đề xong, `srs_card` và `review_log` không đổi một dòng nào |
| `QuizControllerIT` | Testcontainers | hình dạng contract; response **không** chứa đáp án; `quizItemId` lạ → `NOT_FOUND`; thiếu cả `vocabIds` lẫn `count` → lỗi rõ ràng |
| `GeminiClientTest` | WireMock | ba mức timeout được áp đúng |
| `QuizTab.test.tsx` | Vitest + RTL | tạo đề; nộp từng câu; feedback; tổng kết; empty state khi chưa đủ điều kiện; trạng thái đang chấm khoá nút nộp |
| `api-client.test.ts` | Vitest | quá hạn trả `BACKEND_DOWN` `retryable: true` |

---

## 4. Sai lệch so với design gốc

| Mục | Design gốc | Tài liệu này | Lý do |
|---|---|---|---|
| ΔEF khi `AGAIN` | `EF -= 0.2` **và** công thức cho `−0.32` — mâu thuẫn | chỉ dùng công thức: `−0.32` | một nguồn sự thật; `−0.32` là SM-2 chuẩn |
| Tạo `srs_card` | không nói | tự động khi lưu từ đơn; bỏ qua `pos='phrase'` | flashcard cả câu dài không có giá trị ôn |
| Chiều thẻ | không nói | một thẻ, EN → VI | chiều sản sinh để quiz `FREE_WRITE` lo |
| Cascade | không nói | `ON DELETE CASCADE` mọi FK về `vocab_entry` | `DELETE /api/vocab/{id}` đã có từ Phase 1 |
| Đếm từ mới/ngày | không nói | suy từ `review_log.prev_interval = 0` | không cần thêm bảng đếm |
| Ranh giới `quiz`↔`srs` | "quiz không biết lịch ôn tồn tại" **và** chọn theo `srs_card.repetitions` — mâu thuẫn | quiz **đọc** `srs_card`, **không ghi** | hai câu gốc không cùng đúng được; bất biến mới kiểm chứng được bằng test |
| `quiz_item` | không có `prompt_version` | thêm `prompt_version INT` | sửa prompt phải làm đề cũ hết hiệu lực |
| `quiz_attempt` | `user_answer, score, ai_feedback` | thêm `correct BOOLEAN` | `score` không phân biệt "sai" với "chưa chấm" |
| Timeout Gemini | ba mức | tách qua enum + 2 biến môi trường mới | code hiện tại chỉ có một mức |
| Timeout extension | không nói | `AbortSignal.timeout()` trong `ApiClient` | `fetch` trần treo vô hạn |
| Không có ứng viên quiz | không nói | mảng rỗng, không phải lỗi | tránh thêm `ErrorCode` mới |

---

## 5. Thứ tự thực thi

**Plan Phase 2** — kết thúc ở trạng thái ôn tập dùng được thật:
`SrsScheduler` + test bảng → migration `V3` + entity → event tạo card → `SrsService` + hàng đợi → `SrsController` → types/messages/api-client → badge + alarm → `ReviewTab` → Options + README.

**Plan Phase 3** — kết thúc ở trạng thái quiz dùng được thật:
tách timeout Gemini → `AbortSignal` trong `ApiClient` → migration `V4` + entity → `PromptLoader.load(name)` + 3 file prompt → `QuizGenerator` + `QuizItemValidator` → chọn ứng viên + tái dùng item → `QuizGrader` → `QuizService` + `QuizController` → types/messages/api-client → `QuizTab` → README.
