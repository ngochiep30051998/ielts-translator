# IELTS Translator — Chrome Extension + Spring Boot Backend

**Ngày:** 2026-08-03
**Trạng thái:** Design đã duyệt

---

## 1. Mục tiêu

Một Chrome extension cá nhân: bôi đen text trên bất kỳ trang web nào để tra nghĩa hai chiều Việt–Anh qua Gemini, lưu từ mới vào sổ, ôn lại theo spaced repetition, và luyện qua quiz do AI sinh. Định hướng nội dung là tiếng Anh học thuật mức IELTS band 6.5+.

**Người dùng:** một người, chạy toàn bộ trên máy cá nhân. Không đa người dùng, không phát hành Chrome Web Store.

## 2. Phạm vi

**Trong phạm vi**

- Dịch tự động hai chiều: text tiếng Anh → nghĩa tiếng Việt kèm phân tích từ vựng; text tiếng Việt → bản tiếng Anh mức band 6.5+ kèm giải thích.
- Phân biệt tra **từ** và tra **câu**, dùng prompt và schema khác nhau.
- Sổ từ vựng lưu trong PostgreSQL, tìm kiếm, tag, export CSV.
- Spaced repetition theo SM-2 rút gọn, badge nhắc số từ đến hạn.
- Quiz sinh bởi Gemini: điền chỗ trống, chọn collocation, viết câu tự do có AI chấm.

**Ngoài phạm vi (YAGNI)**

- Authentication, multi-tenant, rate limiting — chạy localhost một người.
- Đồng bộ đám mây, `chrome.storage.sync` cho dữ liệu từ vựng — nguồn sự thật duy nhất là PostgreSQL.
- Dịch cả trang, dịch PDF, dịch phụ đề video.
- Offline queue khi backend chết — báo lỗi rõ ràng là đủ.
- E2E test bằng Playwright ở giai đoạn đầu.

## 3. Kiến trúc

```
┌─────────────── Chrome Extension (MV3) ───────────────┐
│  content-script      service-worker      side-panel  │
│  (Shadow DOM         (chủ sở hữu duy      (React:    │
│   bubble, bắt         nhất của network,    Dịch/Sổ   │
│   selection)          badge, alarms)       từ/Ôn/Quiz)│
│                                          options-page │
└──────────────────────────┬───────────────────────────┘
                           │ HTTP JSON
                  http://127.0.0.1:8080
                           │
┌──────────────── Spring Boot (docker compose) ────────┐
│  translation │ vocabulary │ srs │ quiz │ common      │
└──────────────────────────┬───────────────────────────┘
                ┌──────────┴──────────┐
          PostgreSQL 16          Gemini API
```

**Quy tắc kiến trúc bắt buộc:** content script không gọi mạng. Mọi request đi qua service worker. Lý do: tránh CORS và CSP của trang web đích, và giữ một chỗ duy nhất xử lý lỗi, retry, health check.

**Stack:** Java 21 · Spring Boot 3.4 · Maven · PostgreSQL 16 · Flyway · Docker Compose · React 18 + TypeScript + Vite + CRXJS.

## 4. Extension

### 4.1 Thành phần

| Thành phần | Trách nhiệm | Không được làm |
|---|---|---|
| `content-script` | Bắt sự kiện selection, trích câu chứa selection, render bubble trong Shadow DOM, phát âm qua Web Speech API | Gọi HTTP, giữ state lâu dài |
| `service-worker` | Toàn bộ HTTP tới backend, health check, badge, `chrome.alarms`, mở side panel | Render UI |
| `side-panel` (React) | 4 tab: Dịch chi tiết / Sổ từ / Ôn tập / Quiz | Gọi HTTP trực tiếp — đi qua service worker |
| `options-page` (React) | Backend URL, chế độ kích hoạt, giới hạn từ mới/ngày, giọng đọc | — |
| `shared/types` | TypeScript types khớp DTO backend, dùng chung mọi nơi | — |

Bubble render trong **Shadow DOM** để CSS của trang web đích không phá giao diện, và ngược lại.

### 4.2 Message protocol

```ts
// content-script → service-worker
{ type: 'TRANSLATE_SELECTION', text, contextSentence, sourceUrl, pageTitle }
{ type: 'OPEN_PANEL_WITH_RESULT', result }
{ type: 'SAVE_WORD', entry }

// service-worker → content-script
{ type: 'TRANSLATE_RESULT', result }
{ type: 'TRANSLATE_ERROR', code, message, retryable }

// side-panel → service-worker
{ type: 'GET_DUE_CARDS', limit }
{ type: 'SUBMIT_REVIEW', cardId, rating }
{ type: 'SEARCH_VOCAB', query, tag, page }
{ type: 'GENERATE_QUIZ', vocabIds, types }
{ type: 'ANSWER_QUIZ', quizItemId, answer }
```

### 4.3 Hành vi kích hoạt

Mặc định: bôi đen xong, debounce 250ms, bubble tự hiện. Chỉnh được trong Options sang chế độ **chỉ hiện khi bấm phím tắt** (`Alt+T`) cho người thấy tự hiện phiền.

Content script từ chối ngay nếu selection > 1500 ký tự và gợi ý bôi ít hơn — không gửi lên backend.

### 4.4 Extension ID cố định

Sinh sẵn một cặp khoá và nhúng field `key` vào `manifest.json` để extension ID không đổi giữa các lần load unpacked. Backend cấu hình CORS allowlist theo đúng ID này.

## 5. Backend

### 5.1 Modules

| Module | Trách nhiệm | Phụ thuộc |
|---|---|---|
| `translation` | Detect ngôn ngữ và chế độ, chọn prompt, gọi Gemini, cache | `common` |
| `vocabulary` | CRUD sổ từ, tag, tìm kiếm, export CSV | Postgres |
| `srs` | SM-2, hàng đợi due, review log | `vocabulary` |
| `quiz` | Sinh đề, chấm bài | `vocabulary`, `common` |
| `common` | Config, `GeminiClient`, error handling, CORS |  — |

`srs` không biết Gemini tồn tại. `quiz` không biết lịch ôn tồn tại. Ranh giới này giữ cho từng module test được độc lập.

### 5.2 API contract

```
GET    /api/health                → { status, geminiConfigured, dbConnected }

POST   /api/translate
       { text, contextSentence?, sourceUrl?, pageTitle? }
       → { direction: EN_VI|VI_EN, mode: WORD|SENTENCE,
           cached: boolean, payload: <schema mục 6> }

POST   /api/vocab                 → { id, alreadyExists }
GET    /api/vocab?q=&tag=&page=&size=   → Page<VocabEntry>
GET    /api/vocab/{id}            → VocabEntry
DELETE /api/vocab/{id}            → 204
GET    /api/vocab/export.csv      → text/csv

GET    /api/srs/due?limit=        → [CardDto]      (limit mặc định 50)
GET    /api/srs/stats             → { dueCount, newCount, learnedCount }
POST   /api/srs/review
       { cardId, rating: AGAIN|HARD|GOOD|EASY }
       → { nextDueDate, intervalDays, easeFactor }

POST   /api/quiz/generate
       { vocabIds[] | count, types[] }     → [QuizItem]
POST   /api/quiz/answer
       { quizItemId, answer }              → { correct, score, feedback }
```

Mọi lỗi trả cùng một hình dạng: `{ code, message, retryable }`.

Mã lỗi: `GEMINI_QUOTA`, `GEMINI_UNAVAILABLE`, `PARSE_ERROR`, `TEXT_TOO_LONG`, `NOT_FOUND`, `INTERNAL`.

### 5.3 Detect ngôn ngữ và chế độ

Làm ở backend, không ở client — một chỗ duy nhất, test được.

- **Ngôn ngữ:** có ký tự có dấu tiếng Việt → VI. Không dấu thì đối chiếu tập stopword tiếng Việt phổ biến (`của`, `và`, `là`, `không`, `cho`…, cả bản không dấu) so với tỉ lệ từ tiếng Anh. Không quyết được → mặc định EN.
- **Chế độ:** ≤ 3 token → `WORD`, ngược lại `SENTENCE`.

## 6. Prompt và output schema

Prompt lưu ở `src/main/resources/prompts/*.md`, **không hardcode trong Java**. Mỗi file có header `version: N`. Cache key gồm `prompt_version` nên sửa prompt là cache tự invalidate.

Gọi Gemini luôn dùng **structured output** (`responseSchema`) — không bao giờ parse text tự do.

| Chế độ | Trường trong schema |
|---|---|
| **EN→VI, WORD** | `term, lemma, pos, ipa, meaning_vi, definition_en, cefr, band_level, register, collocations[], examples[{en,vi}], synonyms[{term,band}]` |
| **EN→VI, SENTENCE** | `translation_vi, key_vocab[{term, meaning_vi, band_level}], structure_note` |
| **VI→EN, WORD** | `best_en, alternatives[{term, band, register, when_to_use}], collocations[], examples[]` |
| **VI→EN, SENTENCE** | `band65_version, why_notes[], key_phrases[], avoid[]` |

`meaning_vi` và `best_en` phải ngắn — đây là thứ hiển thị trong bubble.

**Hiệu chỉnh band.** Prompt nhúng trực tiếp IELTS descriptors cho Lexical Resource và Grammatical Range mức band 6.5–7, kèm 2–3 few-shot example.

**Rủi ro đã biết:** Gemini tự chấm "đây là band 6.5" không đáng tin — LLM không phải giám khảo IELTS. Nhãn band trong output là **gợi ý tham khảo, không phải sự thật**. Prompt để ngoài file chính là để tune dần khi thấy output lệch. UI không được trình bày band như một con số đã được kiểm chứng.

**Model:** cấu hình qua biến môi trường `GEMINI_MODEL`, mặc định một model Gemini Flash. Đổi model làm thay đổi cache key.

## 7. Data model

```sql
vocab_entry
  id, term, lemma, lang, pos, ipa,
  meaning_vi, definition_en, cefr, band_level,
  tags TEXT[], source_url, source_sentence,
  collocations JSONB, examples JSONB, created_at
  UNIQUE (term, pos)

srs_card
  id, vocab_entry_id FK, ease_factor DEFAULT 2.5,
  interval_days, repetitions, lapses,
  due_date, state (NEW|REVIEW|RELEARNING)

review_log
  id, card_id FK, rating, reviewed_at,
  prev_interval, new_interval

lookup_cache
  id, source_hash UNIQUE, source_text, direction, mode,
  model, prompt_version, response JSONB, hit_count, created_at

quiz_item
  id, vocab_entry_id FK, type, payload JSONB, created_at

quiz_attempt
  id, quiz_item_id FK, user_answer, score, ai_feedback, created_at
```

`collocations` và `examples` để JSONB thay vì bảng con: dữ liệu chỉ đọc theo cụm, không query lẻ. App cá nhân không cần chuẩn hoá tới 3NF.

Migrations quản lý bằng Flyway.

## 8. SRS

Bỏ learning steps trong ngày kiểu Anki (1 phút / 10 phút) — rườm rà với người học chủ động. Chỉ dùng interval theo ngày.

```
Again → repetitions = 0, interval = 1, EF -= 0.2, lapses++, state = RELEARNING
Hard  → interval *= 1.2
Good  → rep 1: 1 ngày | rep 2: 6 ngày | rep 3+: interval *= EF
Easy  → như Good, rồi *= 1.3

EF' = EF + (0.1 - (3-q)·(0.08 + (3-q)·0.02))     với q: AGAIN=0 … EASY=3
sàn EF = 1.3
```

Card mới tạo có `due_date = hôm nay`, `state = NEW`.

Badge trên icon extension hiển thị số card đến hạn. Service worker refresh qua `chrome.alarms` mỗi 30 phút.

Giới hạn mặc định 30 từ mới mỗi ngày, chỉnh trong Options. Card đến hạn không bị giới hạn.

## 9. Quiz

Ba loại, sinh trước và cache vào `quiz_item` — không gọi Gemini mỗi lần mở màn quiz.

`POST /api/quiz/generate` nhận **hoặc** `vocabIds[]` (chỉ định cụ thể) **hoặc** `count` (khi đó backend chọn từ có `srs_card.repetitions ≥ 1`, ưu tiên từ ít `quiz_attempt` nhất, rồi tới từ có `lapses` cao nhất). Từ chưa ôn lần nào không được đưa vào quiz.

| Loại | Cách sinh | Cách chấm |
|---|---|---|
| `FILL_BLANK` | Gemini sinh câu chứa từ, che từ đích | Local: trim, bỏ phân biệt hoa thường, so với đúng dạng đã bị che (không lemmatize) |
| `COLLOCATION_CHOICE` | Gemini sinh 1 đáp án đúng + 3 distractor sai một cách tự nhiên | Local: so index đáp án |
| `FREE_WRITE` | Đề bài là chính từ đó | Gemini chấm: đúng nghĩa / đúng ngữ pháp / có đạt mức 6.5 không + feedback cụ thể |

Chỉ `FREE_WRITE` tốn token khi chấm.

**Quyết định: quiz không tác động tới lịch SRS.** Hai nguồn cùng điều khiển một lịch sẽ khiến interval nhảy khó lần ra nguyên nhân. Quiz chỉ ghi `quiz_attempt`.

## 10. Xử lý lỗi

| Tình huống | Hành vi |
|---|---|
| Backend chưa chạy | Bubble hiện "Backend chưa chạy" + nút Thử lại + link mở Options. Service worker cache kết quả health 30s để không spam |
| Gemini 429 / hết quota | `GEMINI_QUOTA`, hiện rõ cho người dùng, **không** auto-retry |
| Gemini 4xx khác (401/403/404) | `INTERNAL`, `retryable: false`. Key hoặc model sai là lỗi vĩnh viễn — retry vô ích. Message chỉ thẳng vào `GEMINI_API_KEY` / `GEMINI_MODEL` |
| Gemini 5xx hoặc timeout | Retry 1 lần, backoff 1s, sau đó fail |
| Output không khớp schema | Structured output đã ép; nếu vẫn lỗi thì retry 1 lần → `PARSE_ERROR` |
| Selection > 1500 ký tự | Chặn tại content script, gợi ý bôi ít hơn |
| Lưu từ đã có | Upsert theo `(term, pos)`, trả `alreadyExists: true`, panel hiện "Đã có trong sổ" |
| Panel mở khi backend chết | Empty state có nút Thử lại, không crash |

Timeout: dịch 15s · sinh quiz 30s · chấm bài 20s.

## 11. Testing

Trọng tâm đặt vào chỗ sai âm thầm, không phát hiện được bằng mắt.

| Đối tượng | Cách test | Vì sao ưu tiên |
|---|---|---|
| `SrsScheduler` | Unit test dạng bảng: mỗi `rating × state`, sàn EF 1.3, xử lý lapse | Sai ở đây phải cả tháng sau mới lộ |
| `LanguageDetector` | Unit: VI có dấu, VI không dấu, EN, text lẫn lộn | Detect sai làm hỏng toàn bộ trải nghiệm |
| `GeminiClient` | WireMock: 200, 429, 5xx, JSON hỏng, timeout | Đường lỗi không tự nhiên xảy ra khi dev |
| Repository | Testcontainers PostgreSQL | H2 có hành vi JSONB khác — không dùng |
| Controller | `@WebMvcTest` + mock service | Kiểm tra hình dạng contract |
| Extension logic | Vitest: trích câu chứa selection, message protocol | Chỗ dễ sai với DOM thật |
| Panel ôn tập | React Testing Library | Luồng nhiều state |

Không làm E2E Playwright ở giai đoạn đầu: chi phí bảo trì cao, giá trị thấp cho app một người dùng.

## 12. Triển khai

`docker-compose.yml` với 2 service:

- `db` — PostgreSQL 16, volume gắn ngoài để dữ liệu từ vựng sống qua các lần rebuild.
- `app` — Spring Boot, bind **`127.0.0.1:8080`** (không `0.0.0.0` — không phơi ra mạng LAN).

`GEMINI_API_KEY` truyền qua biến môi trường, đọc từ file `.env` không commit. `.env.example` thì có commit.

CORS chỉ cho phép origin `chrome-extension://<extension-id-cố-định>`.

Extension load unpacked từ thư mục `dist/` sau khi `vite build`.

## 13. Cấu hình trong Options

| Mục | Mặc định |
|---|---|
| Backend URL | `http://127.0.0.1:8080` |
| Chế độ kích hoạt | Tự hiện bubble (chọn được: chỉ khi bấm `Alt+T`) |
| Từ mới mỗi ngày | 30 |
| Giọng đọc | Giọng en-US đầu tiên hệ thống có |

## 14. Chia phase

| Phase | Nội dung | Kết quả |
|---|---|---|
| **1** | docker compose + dịch hai chiều + cache + bubble + panel chi tiết + lưu từ + sổ từ | Dùng được hàng ngày |
| **2** | SRS SM-2 + màn ôn tập + badge | Bắt đầu nhớ từ lâu dài |
| **3** | Quiz 3 loại + chấm AI | Luyện chủ động |

Mỗi phase kết thúc ở trạng thái dùng được thật, không phải nửa vời chờ phase sau.
