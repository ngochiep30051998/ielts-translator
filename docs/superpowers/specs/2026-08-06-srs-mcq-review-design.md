# IELTS Translator — Màn ôn tập dạng chọn đáp án

**Ngày:** 2026-08-06
**Trạng thái:** Design đã duyệt
**Tiền đề:** [spec Phase 2 + Phase 3](2026-08-06-phase2-3-srs-quiz-design.md) · Phase 2 đã hiện thực xong (SM-2, hàng đợi ôn, badge, `ReviewTab` dạng thẻ lật)

Tài liệu này **ghi đè mục 2.9** của spec Phase 2: màn ôn tập đổi từ thẻ lật tự chấm sang
trắc nghiệm bốn lựa chọn. Mọi phần khác của Phase 2 (SM-2, hàng đợi, giới hạn từ mới,
badge, API `/api/srs/*`) giữ nguyên.

---

## 1. Phạm vi

**Trong phạm vi:**

- Bỏ hẳn cơ chế tự chấm bốn nút `Lại · Khó · Tốt · Dễ`. Người dùng chọn đáp án; rating
  suy ra từ đúng/sai cộng thời gian trả lời.
- Câu hỏi trộn ngẫu nhiên hai chiều `EN → VI` và `VI → EN`.
- Mồi nhử do Gemini sinh một lần cho mỗi từ rồi cache trong DB.
- Bảng mới `srs_distractor` (`V4`), listener sinh mồi nhử chạy nền, module thuần
  `shared/mcq.ts` phía extension.

**Ngoài phạm vi:**

- Phase 3 Quiz (`FILL_BLANK`, `COLLOCATION_CHOICE`, `FREE_WRITE`) — vẫn là phase riêng,
  vẫn không tác động tới lịch SRS. Tính năng trong tài liệu này **là** màn ôn tập SRS,
  không phải quiz.
- Thống kê độ chính xác, biểu đồ tiến độ.
- Sửa công thức SM-2. `SrsScheduler` không đổi một dòng nào.

---

## 2. Vì sao phải có mồi nhử sinh sẵn

Sổ từ hiện có 8 từ. Nếu lấy mồi nhử từ chính sổ, bốn lựa chọn sẽ là bốn nghĩa không
liên quan gì nhau — người học loại trừ được ngay mà không cần nhớ nghĩa, và cùng một
bộ nghĩa lặp lại sau vài lượt. Mồi nhử có giá trị phải **gần đúng nhưng sai**, thứ chỉ
sinh được bằng mô hình ngôn ngữ.

Vì vậy: Gemini sinh mồi nhử, DB cache lại. Mỗi từ tốn đúng một call trong suốt vòng
đời, trừ khi prompt đổi version.

---

## 3. Backend

### 3.1 Migration `V4__srs_distractor.sql`

```sql
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

`vi_options` — 3 nghĩa tiếng Việt sai, dùng cho câu hỏi chiều `EN → VI`.
`en_options` — 3 từ tiếng Anh sai, dùng cho chiều `VI → EN`.

`prompt_version` theo đúng nguyên tắc của `lookup_cache`: sửa nội dung prompt phải tăng
`version:` trong file, và bản ghi có version cũ coi như không có — đây là cách duy nhất
làm mồi nhử cũ hết hiệu lực.

`UNIQUE` trên `vocab_entry_id`: mỗi từ đúng một bản ghi, sinh lại thì ghi đè.
`ON DELETE CASCADE`: xoá từ trong sổ không để lại rác.

**Không backfill trong migration.** Sinh mồi nhử là gọi mạng; migration phải chạy được
khi không có mạng và không có `GEMINI_API_KEY`. Từ cũ được bù dần theo mục 3.4.

Entity `SrsDistractor` map hai cột JSONB bằng hypersistence-utils (`@Type(JsonType.class)`),
đúng cách `VocabEntry` đang map `tags`/`collocations`.

### 3.2 Prompt `prompts/srs-distractors.md`

Header `version: 1`. Một call sinh cả hai chiều:

```
{ vi_options: [string, string, string],
  en_options: [string, string, string] }
```

Yêu cầu trong prompt: mồi nhử phải **cùng loại từ và cùng miền nghĩa** với đáp án đúng
để không loại trừ được bằng ngữ pháp; **không được trùng hoặc đồng nghĩa** với đáp án
đúng; `en_options` là từ tiếng Anh có thật, không bịa.

`PromptLoader` thêm `load(String name)` đọc theo tên file; `load(Direction, Mode)` hiện
có trở thành lớp mỏng gọi vào nó. Không đổi hành vi của bốn prompt dịch.

### 3.3 `DistractorGenerator` — chạy nền, không chặn việc lưu từ

`SrsCardCreator` hiện chạy **đồng bộ trong cùng transaction** với lệnh lưu từ. Gắn thêm
call Gemini vào đó sẽ làm thao tác lưu treo tới 15s, và Gemini lỗi sẽ rollback cả việc
lưu từ. Đó là lý do đây phải là listener **riêng**:

```java
@TransactionalEventListener(phase = AFTER_COMMIT)
@Async("srsTaskExecutor")
public void onVocabEntrySaved(VocabEntrySavedEvent event)
```

- Sau commit: từ đã nằm chắc trong sổ trước khi gọi mạng.
- Bất đồng bộ: response của `POST /api/vocab` không chờ Gemini.
- Bỏ qua `pos = 'phrase'` — giống `SrsCardCreator`, câu không làm trắc nghiệm được.
- Gemini lỗi: log warn rồi thôi. Không ném lên người dùng — người dùng đang không đứng
  chờ việc này.

Bật `@EnableAsync` và khai một `ThreadPoolTaskExecutor` tên `srsTaskExecutor` trong
`common`: core 1, max 2, queue 50, `CallerRunsPolicy`. Hàng đợi có chặn để một đợt lưu
hàng loạt không sinh ra hàng trăm call Gemini song song. Không thêm dependency.

### 3.4 Bù cho từ cũ và cho lần Gemini hỏng

`SrsService.due()` sau khi dựng xong hàng đợi: thẻ nào chưa có `srs_distractor` hợp lệ
(chưa có bản ghi, hoặc `prompt_version` khác version hiện hành) thì bắn một lượt sinh
nền, tối đa **10 từ** mỗi lần gọi, rồi trả hàng đợi về ngay — **không chờ**.

`DistractorGenerator` giữ một `Set` các `vocabEntryId` đang sinh dở
(`ConcurrentHashMap.newKeySet()`) để mở tab ôn nhiều lần không xếp chồng call cho cùng
một từ.

Cơ chế này giải quyết ba chuyện bằng một đường: 8 từ đã có sẵn trong sổ, từ mà Gemini
lỗi lúc lưu, và mọi từ có mồi nhử hết hiệu lực sau khi tăng version prompt.

Lượt ôn ngay lúc đó vẫn chạy được — mục 4.2 nói cách bù mồi nhử phía extension.

### 3.5 `DistractorValidator` — hàm thuần

Gemini trả rác là chuyện xảy ra thật dù đã dùng structured output. Validator loại cả
bản ghi (không lưu gì, để lần sau sinh lại) khi bất kỳ điều nào sau đây sai:

- `vi_options` và `en_options` mỗi mảng đúng **3** phần tử.
- Không phần tử nào rỗng hoặc chỉ có khoảng trắng.
- Trong cùng một mảng không có hai phần tử trùng nhau (so sánh sau khi trim, bỏ phân
  biệt hoa thường).
- Không phần tử nào trùng đáp án đúng — `vi_options` không được chứa `meaningVi`,
  `en_options` không được chứa `term`. Đây là lỗi Gemini hay mắc nhất và cũng là lỗi
  giết chết bài ôn: hai lựa chọn cùng đúng.

Không ném `PARSE_ERROR`. Đây là việc chạy nền, không có ai đang chờ để nhận lỗi.

### 3.6 API

**Không thêm endpoint.** `CardDto` thêm hai field:

```java
List<String> viDistractors,   // rỗng khi chưa sinh
List<String> enDistractors
```

`POST /api/srs/review` giữ nguyên hợp đồng `{ cardId, rating }` → `ReviewResponse`.
Extension tự suy ra rating rồi gửi lên; backend không biết câu hỏi là trắc nghiệm.

**Vì sao luật chấm nằm ở extension, không ở backend:** thời gian trả lời chỉ đo được ở
client. Gửi `{ correct, elapsedMs }` lên rồi backend suy ra rating sẽ phải đổi hợp đồng
API, thêm nhánh vào `SrsService`, mà vẫn không kiểm chứng được gì hơn — luật chấm là
chính sách của giao diện, không phải của thuật toán lịch. Để ở `shared/mcq.ts` thì nó
là hàm thuần, test bằng bảng trong Vitest.

---

## 4. Extension

### 4.1 `shared/mcq.ts` — module thuần

Không React, không `chrome.*`, không `Math.random` gọi trực tiếp. Toàn bộ luật chơi nằm
ở đây để test được bằng bảng.

```ts
export type QuizDirection = 'EN_VI' | 'VI_EN';

export interface Question {
  direction: QuizDirection;
  card: CardDto;
  options: string[];    // đã trộn
  correctIndex: number;
}

export function buildQuestion(
  card: CardDto, pool: CardDto[], random: () => number,
): Question | null;

export function ratingFor(correct: boolean, elapsedMs: number): Rating;
```

`random` tiêm vào để test tất định. Mặc định `Math.random` do `ReviewTab` truyền.

### 4.2 `buildQuestion`

1. Bốc ngẫu nhiên một chiều.
2. Đáp án đúng: `card.meaningVi` (chiều `EN_VI`) hoặc `card.term` (chiều `VI_EN`).
3. Mồi nhử: lấy `card.viDistractors` / `card.enDistractors`. Thiếu bao nhiêu thì bù
   bấy nhiêu bằng `meaningVi` / `term` của các thẻ **khác** trong `pool` — đây là cách
   ôn vẫn chạy được khi mồi nhử chưa sinh kịp.
4. Loại mọi mồi nhử trùng đáp án đúng (so sánh trim, bỏ phân biệt hoa thường) và trùng
   nhau. Cắt còn tối đa 3.
5. Trộn đáp án đúng vào, trả `correctIndex`.
6. Không dựng nổi **tối thiểu 2** lựa chọn → trả `null`.

`pool` là chính hàng đợi đang nạp trong panel, không phải một request mới.

### 4.3 `ratingFor`

| Kết quả | Rating |
|---|---|
| Sai, bất kể nhanh chậm | `AGAIN` |
| Đúng, `t < 5s` | `EASY` |
| Đúng, `5s ≤ t < 15s` | `GOOD` |
| Đúng, `15s ≤ t ≤ 60s` | `HARD` |
| Đúng, `t > 60s` | `GOOD` |

Bốn khoảng đúng là rời nhau và phủ kín, không có chỗ nào phải xét thứ tự dòng.

Đồng hồ chạy từ lúc câu hỏi render tới lúc bấm lựa chọn.

Mốc 60s không phải trường hợp thừa: quá 60 giây nghĩa là người dùng rời máy chứ không
phải nhớ chật vật, chấm `HARD` lúc đó là phạt oan. Trên mốc đó thì bỏ tín hiệu thời
gian và coi như `GOOD`.

Luật này dùng đủ bốn mức, nên `EF` còn đường hồi phục (`EASY` +0.10). Nếu chỉ có
`GOOD`/`AGAIN` thì `ΔEF` chỉ có thể là 0 hoặc −0.32 — mọi thẻ sẽ tụt dần về sàn 1.3 và
khoảng cách ôn teo lại vĩnh viễn.

Lưu ý đã biết từ spec Phase 2: `EASY` trên thẻ `NEW` vẫn ra 1 ngày vì
`round(1 × 1.3) = 1`. Đúng công thức, không phải lỗi.

### 4.4 `ReviewTab.tsx` — viết lại

Bỏ state `revealed` và mảng `RATINGS`. Luồng một thẻ:

1. Tiến độ `3/8`, rồi câu hỏi.
   - `EN → VI`: hiện `term`, `ipa`, nút 🔊.
   - `VI → EN`: hiện `meaningVi`. **Không** hiện `term`, **không** có nút phát âm —
     phát âm chính là đọc to đáp án.
2. Bấm một lựa chọn → khoá toàn bộ lựa chọn, tô đáp án đúng, tô đỏ ô đã chọn nếu sai,
   mở phần chi tiết (`pos`, `cefr`, `bandLevel`, `definitionEn`), đồng thời gửi
   `SUBMIT_REVIEW` với rating suy từ `ratingFor`.
3. Nút **Tiếp** sang thẻ sau. Không tự nhảy — người học cần thời gian đọc phần chi tiết.
4. Phím tắt: phím số `1` tới `n` với `n` là số lựa chọn đang hiện (2, 3 hoặc 4); phím
   số ngoài khoảng đó không làm gì. `Enter` sang thẻ sau, chỉ có tác dụng sau khi đã
   chọn.
5. `SUBMIT_REVIEW` lỗi → **giữ nguyên thẻ**, hiện nút Thử lại gửi lại đúng rating đó.
   Giữ nguyên hành vi Phase 2 đã có test.
6. Một thẻ chỉ gửi đúng một `SUBMIT_REVIEW`: sau khi đã chọn, các lựa chọn bị khoá.
7. `buildQuestion` trả `null` cho một thẻ → **bỏ qua thẻ đó**, sang thẻ kế, không gửi
   `SUBMIT_REVIEW` (chưa ôn thì không được đổi lịch). Chỉ khi cả hàng đợi không dựng
   được câu nào mới hiện empty state: "Chưa tạo được câu hỏi — mồi nhử đang được sinh,
   thử lại sau ít phút." kèm nút Tải lại.

   Trường hợp này chỉ xảy ra khi thẻ chưa có mồi nhử **và** hàng đợi không còn thẻ nào
   khác để bù. Với sổ từ đã có vài từ thì thực tế không gặp; nó là đường lui cho lần
   đầu dùng, khi sổ mới có đúng một từ.

Panel vẫn nạp cả xấp một lần rồi ôn trong bộ nhớ, không refetch giữa chừng — giữ nguyên
mục 2.9 spec Phase 2.

### 4.5 Chỗ khác phải sửa theo

| File | Nội dung |
|---|---|
| `shared/types.ts` | `CardDto` thêm `viDistractors`, `enDistractors` |
| `sidepanel/styles.css` | style lựa chọn, trạng thái đúng/sai, phần chi tiết |
| `README.md` | mục "Ôn tập" — bảng bốn nút hiện tại mô tả sai hoàn toàn |
| spec Phase 2/3 mục 2.9 | ghi chú trỏ sang tài liệu này |

Không đổi `shared/messages.ts`, `background/api-client.ts`, `background/badge.ts`,
`service-worker.ts`, `manifest.config.ts`.

---

## 5. Test

| Đối tượng | Kiểu | Nội dung |
|---|---|---|
| `DistractorValidatorTest` | unit, không Docker | loại khi thiếu phần tử, thừa phần tử, phần tử rỗng, trùng nhau, trùng `meaningVi`, trùng `term`; nhận bản ghi hợp lệ |
| `DistractorGeneratorIT` | Testcontainers + WireMock | sinh và lưu đúng `prompt_version`; Gemini lỗi không làm hỏng việc lưu từ; `pos='phrase'` không sinh; sinh lại ghi đè bản cũ; từ đang sinh dở không bị xếp chồng call |
| `SrsDistractorMigrationIT` | Testcontainers | `V4` dựng bảng đúng; xoá `vocab_entry` cascade sạch `srs_distractor` |
| `SrsControllerIT` | Testcontainers | `CardDto` có `viDistractors`/`enDistractors`; rỗng khi chưa sinh |
| `mcq.test.ts` | Vitest | bảng `ratingFor` đủ năm dòng kể cả mốc 60s; `buildQuestion` tất định với `random` giả; đủ 4 lựa chọn khi có mồi nhử; bù từ `pool` khi thiếu; không lựa chọn nào trùng đáp án; trả `null` khi `pool` cạn; cả hai chiều đều dựng được |
| `ReviewTab.test.tsx` | Vitest + RTL | viết lại: chiều `VI → EN` không lộ `term`; chọn đúng nhanh gửi `EASY`; chọn sai gửi `AGAIN`; một thẻ chỉ gửi một `SUBMIT_REVIEW`; thẻ không dựng được câu bị bỏ qua và **không** gửi `SUBMIT_REVIEW`; lỗi giữ nguyên thẻ và có nút Thử lại; hết bài hiện empty state |

Thời gian trong test `ReviewTab` điều khiển bằng fake timer của Vitest, không `sleep` thật.

---

## 6. Ghi đè spec trước

| Spec Phase 2/3 | Ghi đè |
|---|---|
| Mục 2.9 "Màn ôn tập" — thẻ lật, nút "Hiện đáp án", bốn nút tự chấm, chiều `EN → VI` | Thay bằng trắc nghiệm trộn hai chiều, rating suy ra tự động (mục 4 tài liệu này) |
| Mục 2.10, dòng `ReviewTab.test.tsx` | Thay bằng dòng tương ứng ở mục 5 |

Phase 3 Quiz **không** bị ảnh hưởng: `COLLOCATION_CHOICE` vẫn là loại quiz riêng, vẫn
không ghi vào `srs_card`/`review_log`. Bảng `srs_distractor` thuộc module `srs`, khác
bảng `quiz_item` của Phase 3 cả về mục đích lẫn vòng đời.

---

## 7. Ràng buộc giữ nguyên

- `vocabulary` không import gì từ `srs`. Việc sinh mồi nhử bám vào
  `VocabEntrySavedEvent` đã có, không thêm gì ở `vocabulary`.
- Không thêm dependency. `@EnableAsync` và `ThreadPoolTaskExecutor` là Spring core.
- Migration append-only: `V4` mới, không sửa `V1`–`V3`.
- Không thêm `ErrorCode` mới.
- Text hiển thị và comment viết tiếng Việt đủ dấu.
- `npm run build` là nơi duy nhất chạy type check — test xanh mà build đỏ vẫn là hỏng.
