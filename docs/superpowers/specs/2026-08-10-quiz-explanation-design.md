# Giải thích đáp án quiz

**Ngày:** 2026-08-10
**Trạng thái:** Design đã duyệt
**Phạm vi:** `backend/` + `extension/`. Thêm một endpoint, không có migration Flyway, không
tăng version prompt nào đang có.

---

## 1. Vấn đề

Trả lời xong một câu quiz thì người học chỉ nhận được đúng hai thứ: đúng/sai kèm điểm, và
một chuỗi `feedback` ghép cứng trong `QuizService`:

```java
correct ? "Chính xác." : "Chưa đúng. Đáp án: " + expected
```

Biết đáp án là "allocate" không dạy được gì. Không biết vì sao "allocate" đúng, không biết
vì sao cụm mình vừa chọn thì sai, không biết câu tiếng Anh đó nghĩa là gì. `FREE_WRITE` khá
hơn — có nhận xét tiếng Việt và câu viết lại do Gemini chấm — nhưng câu viết lại vẫn là
tiếng Anh không kèm bản dịch.

## 2. Hành vi mới

Sau khi trả lời **bất kỳ** câu nào, khối kết quả có thêm nút `Giải thích`. Bấm mới gọi
Gemini; không bấm thì không tốn gì.

```
┌────────────────────────────────┐
│ ✗ Chưa đúng · 0 điểm           │
│ Chưa đúng. Đáp án: allocate    │
│                                │
│        [ Giải thích ]          │
└────────────────────────────────┘
        ↓ bấm, chờ 1–2 giây
┌────────────────────────────────┐
│ ✗ Chưa đúng · 0 điểm           │
│ Chưa đúng. Đáp án: allocate    │
│                                │
│ ── Giải thích ───────────────  │
│ "allocate" là phân bổ nguồn    │
│ lực có kế hoạch. Chủ ngữ "the  │
│ government" + tân ngữ          │
│ "resources" nên chỉ "allocate" │
│ hợp ngữ cảnh; "distribute" bạn │
│ điền thiên về chia đều.        │
│                                │
│ ── Nghĩa đáp án ─────────────  │
│ allocate = phân bổ, cấp phát   │
│                                │
│ ── Dịch câu ─────────────────  │
│ The government must allocate   │
│ resources efficiently.         │
│ Chính phủ phải phân bổ nguồn   │
│ lực một cách hiệu quả.         │
│                                │
│           [ Tiếp ]             │
└────────────────────────────────┘
```

Nút hiện **cả khi trả lời đúng và khi bỏ qua câu**. Đoán mò mà trúng vẫn cần biết vì sao
trúng; bỏ qua thì càng cần.

Nội dung **bám theo câu trả lời của người học**, không phải giải thích chung chung: chọn sai
thì nói vì sao cụm vừa chọn không tự nhiên, điền sai thì so từ đã điền với đáp án. Trả lời
đúng thì chỉ giải thích đáp án.

## 3. Hợp đồng API

### `POST /api/quiz/explain`

Request:

```json
{ "quizItemId": 42 }
```

Chỉ có `quizItemId`. **Không gửi kèm câu trả lời**, dù panel đang giữ nó: backend tự đọc
`quiz_attempt` gần nhất của item. Đó không phải chuyện tiết kiệm byte mà là chốt chặn an
toàn — endpoint này **tiết lộ đáp án**, nên nó phải từ chối khi chưa có lượt làm nào. Nhận
đáp án từ client rồi tin luôn sẽ biến `/explain` thành đường vòng đọc đáp án trước khi trả
lời, phá đúng thứ mà `QuizItemDto` cố ý bảo vệ.

Response — `ExplanationDto`:

```json
{
  "explanation": "\"allocate\" là phân bổ nguồn lực có kế hoạch…",
  "answerMeaning": "allocate = phân bổ, cấp phát",
  "sentenceEn": "The government must allocate resources efficiently.",
  "sentenceVi": "Chính phủ phải phân bổ nguồn lực một cách hiệu quả."
}
```

Ý nghĩa từng field theo loại câu hỏi:

| field | FILL_BLANK | COLLOCATION_CHOICE | FREE_WRITE |
|---|---|---|---|
| `explanation` | vì sao đáp án đúng, so với từ người học đã điền | vì sao cụm đúng tự nhiên, vì sao cụm người học chọn thì không | cách dùng từ, câu người học viết lệch chỗ nào |
| `answerMeaning` | nghĩa của từ đáp án **trong ngữ cảnh câu** | nghĩa của cả cụm đúng | nghĩa của từ phải dùng |
| `sentenceEn` | câu đề bài đã điền đáp án — **ghép ở Java**, không nhờ Gemini | câu ví dụ ngắn Gemini sinh, chứa cụm đúng | `improvedVersion` của lượt làm; null thì lấy câu người học viết |
| `sentenceVi` | bản dịch tiếng Việt của `sentenceEn` (Gemini) | | |

- `explanation` và `answerMeaning` **luôn** non-null và khác rỗng.
- `sentenceEn` và `sentenceVi` là **một cặp**: cùng null hoặc cùng non-null. Cùng null xảy
  ra đúng một trường hợp — `FREE_WRITE` bị bỏ qua (câu trả lời rỗng nên không có
  `improvedVersion`, cũng không có câu người học). Panel không render khối "Dịch câu" khi
  null.
- **Bỏ qua câu `FILL_BLANK` hoặc `COLLOCATION_CHOICE`** (câu trả lời rỗng) vẫn giải thích
  bình thường và vẫn có đủ cặp câu — chỉ khác ở chỗ `explanation` không có lựa chọn nào của
  người học để đối chiếu, nên nó chỉ giải thích đáp án. Prompt phải chịu được `{{ANSWER}}`
  rỗng thay vì sinh ra câu kiểu "bạn đã chọn ''".
- `answerMeaning` lấy nghĩa **trong ngữ cảnh** chứ không chép `VocabEntry.meaningVi`, nhưng
  `meaningVi` được đưa vào prompt làm ngữ cảnh để bản giải thích không mâu thuẫn với sổ từ
  của chính người dùng.

Lỗi đi đúng đường `{code, message, retryable}` sẵn có, **không thêm `ErrorCode` mới** nên
`GlobalExceptionHandler.statusFor()` không phải đụng tới:

| tình huống | mã | HTTP |
|---|---|---|
| `quizItemId` không tồn tại | `NOT_FOUND` | 404 |
| item tồn tại nhưng chưa có lượt làm nào | `NOT_FOUND` | 404 |
| Gemini hết quota | `GEMINI_QUOTA` | 429 |
| Gemini chết / timeout | `GEMINI_UNAVAILABLE` | 503 |

## 4. Vì sao gọi lúc bấm nút, không sinh sẵn lúc tạo đề

Hướng còn lại là nhét `explanation`/`translation` vào chính prompt sinh đề, lưu vào
`quiz_item.payload`, trả kèm lúc chấm. Nó nhanh hơn (hiện tức thì) và không tốn call thêm.

Đổi lại, sửa nội dung prompt sinh đề bắt buộc phải tăng `version:` (ràng buộc #5), mà
`prompt_version` nằm trong điều kiện `findReusable` — nên **mọi đề đã sinh sẵn nhưng chưa
làm trong DB đều hết hiệu lực ngay**, và lần tạo đề đầu tiên sau khi deploy phải sinh lại
toàn bộ. Nó cũng sinh giải thích cho cả những câu người học không bao giờ mở ra đọc.

Hướng đã chọn không đụng vào `promptVersionFor()`, nên **không có item nào bị mất hiệu lực**.
Chi phí là 1 call Gemini mỗi lần bấm nút, và người học chỉ trả chi phí đó khi thật sự muốn
đọc.

## 5. Backend

**Không có migration Flyway. Không lưu giải thích vào DB.** Không có gì đọc lại nó, và mỗi
`quiz_item` chỉ được làm đúng một lần (`findReusable` loại item đã có attempt) nên không tồn
tại kịch bản "giải thích lại câu cũ" để mà cache. Thêm cột chỉ để đấy là chi phí thuần.

Thêm mới:

- **Ba file prompt**, mỗi file `version: 1`:
  `quiz-explain-fill-blank.md`, `quiz-explain-collocation.md`, `quiz-explain-free-write.md`.
  Ba file chứ không một, theo đúng lối đã có của repo (mỗi hình dạng việc một file) — ba loại
  có input khác hẳn nhau: câu chứa `___`, bốn lựa chọn, bài viết tự do.
- `ExplanationDto` — record 4 field ở mục 3.
- `ExplainQuizRequest` — record, `@NotNull Long quizItemId`.
- `QuizAttemptRepository.findFirstByQuizItem_IdOrderByIdDesc(Long)`.
- `QuizService.explain(Long quizItemId)`.
- `QuizController.explain(@Valid @RequestBody ExplainQuizRequest)` — thiếu `@Valid` là vô
  hiệu ràng buộc trong im lặng, đúng cảnh báo đã ghi ở `generate()`.

Luồng của `QuizService.explain`:

1. Nạp `QuizItem`; không có → `NOT_FOUND`.
2. Nạp lượt làm gần nhất; không có → `NOT_FOUND` **trước khi gọi Gemini** (không đốt quota
   cho một request đang cố đọc trộm đáp án).
3. `switch` trên `QuizType`, **không nhánh `default`** — thêm loại mới sau này phải fail
   compile ở đây, đúng lối `toDto()` và `GlobalExceptionHandler.statusFor()`.
4. Dựng prompt theo loại, có nhét câu trả lời của người học vào.
5. `gemini.generateJson(prompt, EXPLAIN_SCHEMA, GeminiTimeout.QUIZ_GRADE)`.
6. Ghép `sentenceEn` (Java biết với FILL_BLANK và FREE_WRITE) với phần Gemini trả.

**Dùng lại `GeminiTimeout.QUIZ_GRADE`**, không thêm mức mới: output cùng cỡ với chấm bài
(vài trăm token), và thêm giá trị enum kéo theo một mục cấu hình timeout mới trong
`application.yml` cho không nhiều lợi ích.

`EXPLAIN_SCHEMA` **chỉ bắt buộc** `explanation_vi` và `answer_meaning_vi` — đúng hai field
mà mọi loại, mọi tình huống đều phải có.

`sentence_en` không bắt buộc: với `FILL_BLANK` và `FREE_WRITE` backend đã biết câu tiếng Anh
nên tự điền — nhờ Gemini chép lại một chuỗi backend đang cầm là mời nó chép sai. Chỉ
`COLLOCATION_CHOICE` mới thật sự cần Gemini nghĩ ra câu ví dụ.

`sentence_vi` cũng không bắt buộc, vì có đúng một trường hợp **không tồn tại câu nào để
dịch**: `FREE_WRITE` bị bỏ qua. Bắt buộc field này sẽ ép Gemini bịa ra một câu tiếng Việt
không gắn với câu tiếng Anh nào. Quy tắc ghép cuối cùng: **thiếu một nửa thì bỏ cả cặp** —
`sentenceEn` rỗng hoặc `sentenceVi` rỗng thì cả hai cùng về null, panel không render khối
"Dịch câu". Không bao giờ trả một nửa cặp.

## 6. Extension

`shared/types.ts` — gương của DTO:

```ts
export interface QuizExplanation {
  explanation: string;
  answerMeaning: string;
  /** Cặp đôi với sentenceVi: cùng null (FREE_WRITE bỏ qua câu) hoặc cùng non-null. */
  sentenceEn: string | null;
  sentenceVi: string | null;
}
```

`shared/messages.ts` — đủ ba bước của ràng buộc #2:

```ts
export interface ExplainQuizRequest {
  type: 'EXPLAIN_QUIZ';
  quizItemId: number;
}
```

thêm vào union `ExtensionRequest` **và** `ResponseMap` (`EXPLAIN_QUIZ: QuizExplanation`).
`api-client.ts` thêm `explainQuiz()` gọi `POST /api/quiz/explain`; `service-worker.ts` thêm
một `case`.

`QuizTab.tsx` — ba state mới:

```ts
const [explanation, setExplanation] = useState<QuizExplanation | null>(null);
const [explaining, setExplaining] = useState(false);
const [explainError, setExplainError] = useState<ApiError | null>(null);
```

**Một ô chứ không phải mảng song song với `results`.** Điều hướng chỉ đi tới — `next()` không
có đường lùi — nên không bao giờ quay lại câu cũ. `results` là mảng vì màn tổng kết đếm số
câu đúng; giải thích không vào tổng kết. Xoá cả ba ở `next()`, `reset()` và `generate()`.

Khối render nằm **trong** nhánh `answered`, sau `improvedVersion`, trước nút "Tiếp": nút
`Giải thích` (nhãn đổi thành `Đang giải thích…` khi chạy) → ba khối `Giải thích` /
`Nghĩa đáp án` / `Dịch câu`. Khối "Dịch câu" hiện `sentenceEn` rồi `sentenceVi`, và chỉ
render khi cặp đó non-null.

**Nút "Tiếp" bị khoá trong lúc đang giải thích.** Không khoá thì bấm "Tiếp" khi request đang
bay sẽ làm response về muộn ghi giải thích của câu cũ lên câu mới — sai câu, và không có lỗi
nào nổ ra. Khoá nút xoá hẳn lớp race đó thay vì đi canh nó bằng ref hay so id. Người vừa bấm
"Giải thích" là người đang muốn đọc, nên chờ 1–2 giây không mất gì; response lỗi cũng kết
thúc `explaining` nên không có đường kẹt vĩnh viễn.

Lỗi hiện dưới nút, kèm chữ `Bấm "Giải thích" để thử lại.` — nút vẫn bấm lại được.

`styles.css`: thêm `.quiz-explain` (nút), `.quiz-explanation` (khối), `.quiz-sentence-en`.
CSS viết tay, cùng lối với các `.quiz-*` sẵn có.

## 7. Test

### Backend

`QuizExplainIT extends AbstractPostgresIT`, giả lập Gemini bằng `@MockitoBean GeminiClient`
— đúng lối `QuizControllerIT` đang dùng. (WireMock chỉ xuất hiện ở `GeminiClientTest`, nơi
thứ đang test chính là tầng HTTP.)

1. `FILL_BLANK` trả lời sai → 200, `sentenceEn` là câu đề bài đã thay `___` bằng đáp án
   (chuỗi do Java ghép, không phải chuỗi Gemini trả).
2. `COLLOCATION_CHOICE` → `sentenceEn` lấy từ Gemini.
3. `FREE_WRITE` có `improvedVersion` → `sentenceEn` đúng bằng chuỗi đó.
4. `FREE_WRITE` bỏ qua câu → `sentenceEn` và `sentenceVi` **cùng** null.
5. `FILL_BLANK` bỏ qua câu (lượt làm có `user_answer` rỗng) → vẫn 200 và vẫn đủ cặp câu;
   bỏ qua không phải lý do để mất phần dịch.
6. Gemini trả `sentence_vi` rỗng cho `COLLOCATION_CHOICE` → cả cặp về null, không trả một
   nửa.
7. Item chưa có lượt làm → 404 `NOT_FOUND`, **và `geminiClient` không nhận call nào** — vừa chứng
   minh không đốt quota, vừa chứng minh không có đường vòng đọc đáp án trước khi trả lời.
8. `quizItemId` lạ → 404.
9. Gemini 503 → `GEMINI_UNAVAILABLE`, `retryable: true`.
10. Verify prompt truyền vào `geminiClient.generateJson` **có chứa câu trả lời của người học** — đó là điều kiện để
   "chỉ thẳng chỗ sai" là thật, chứ không phải một lời hứa nằm trong prompt.

`PromptLoaderTest.loadsQuizPrompts` mở rộng cho ba file explain mới: đọc được, `version`
dương, có đủ placeholder.

### Extension

`QuizTab.test.tsx`:

- Chưa trả lời → không có nút "Giải thích".
- Trả lời **đúng** → vẫn có nút.
- Bấm → gửi đúng `{ type: 'EXPLAIN_QUIZ', quizItemId }`, render đủ ba khối.
- `sentenceEn`/`sentenceVi` null → không render khối "Dịch câu".
- Lỗi → hiện thông báo, nút vẫn bấm lại được.
- Đang giải thích → nút "Tiếp" bị khoá.
- Sang câu mới → khối giải thích lẫn thông báo lỗi biến sạch.

`api-client.test.ts` và `service-worker.test.ts`: route và `case` mới.

### Bằng chứng trước khi báo xong

`mvn test`, `npm test`, **và** `npm run build` — nơi duy nhất chạy type check.

## 8. Ngoài phạm vi

- Không lưu giải thích vào DB, không có lịch sử giải thích.
- Không cache phía server: mỗi `quiz_item` chỉ làm một lần nên không có gì để cache lại.
- Không đụng vào `feedback` hiện có của `/api/quiz/answer`; nó vẫn là kênh báo đáp án đúng.
- Không đổi prompt sinh đề, không đổi `promptVersionFor()`, không đổi hình dạng
  `QuizItemDto` hay `AnswerResultDto`.
