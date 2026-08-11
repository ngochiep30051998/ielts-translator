# Màn thống kê tiến độ học

**Ngày:** 2026-08-11
**Trạng thái:** Design đã duyệt
**Phạm vi:** `api-service/` + `extension/`. Thêm một endpoint đọc, một tab side panel.
**Không có migration, không bảng mới, không cột mới, không tăng version prompt nào.**

---

## 1. Vấn đề

Người học ôn thẻ và làm quiz mỗi ngày nhưng không nhìn thấy gì về chính mình. Hệ thống
biết tất cả — `review_log` ghi từng lượt ôn kèm rating và mốc thời gian từ Phase 2,
`quiz_attempt` ghi từng câu quiz kèm đúng/sai và điểm từ Phase 3 — nhưng không có màn hình
nào đọc hai bảng đó. Dữ liệu vào rồi nằm im.

Điều đó lấy mất thứ giữ người ta học đều: cảm giác chuỗi ngày không muốn làm đứt.

**Nói rõ ngay để tránh hiểu nhầm về phạm vi:** yêu cầu ban đầu là "lưu trữ kết quả ôn tập
và kết quả làm bài quiz". Phần lưu trữ **đã xong từ trước** — hai bảng trên đã ghi đủ. Việc
thật của tài liệu này là **tổng hợp và hiển thị**. Không có gì mới được ghi xuống DB.

## 2. Hành vi mới

Tab thứ 5 tên **Thống kê**, cạnh Dịch / Sổ từ / Ôn tập / Quiz. Bốn khối xếp dọc:

```
┌──────────────────────────────────────┐
│  🔥 5        23        1284     312  │   ← streak hiện tại, dài nhất,
│  ngày liên  kỷ lục   lượt ôn    từ   │      tổng lượt ôn, số từ đã học
│  tiếp                          đã học│
├──────────────────────────────────────┤
│  30 ngày gần nhất                    │
│      ▁▃█▅▂ ▁▇█▃ ▁▅█▇▂▁ ▃█▅▁          │   ← cột theo ngày
├──────────────────────────────────────┤
│  91 ngày gần nhất                    │
│  T2 ░░▓█░▓░░█▓░░▓                    │
│  T3 ░█▓░░▓█░░▓█░░                    │   ← heatmap lịch
│  ...                                 │
│  CN ░░░▓░░█░░░▓░░                    │
├──────────────────────────────────────┤
│  Độ chính xác                        │
│  Tỉ lệ nhớ khi ôn        84%         │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░  (4 mức rating)  │
│  Điền từ vào chỗ trống   31/40  78%  │
│  Chọn cụm đi với nhau    18/22  82%  │
│  Tự viết câu              9/15  60%  │
│    điểm trung bình          72/100   │
└──────────────────────────────────────┘
```

Không có gì bấm được ngoài nút *Thử lại* khi lỗi. Đây là màn đọc.

## 3. Quyết định phạm vi

Bốn lựa chọn đã chốt lúc brainstorm, ghi lại vì mỗi cái loại bỏ một nhánh việc lớn:

| Câu hỏi | Chốt | Hệ quả |
|---|---|---|
| Mục đích chính | **Động lực học đều** | Bỏ nhánh chẩn đoán điểm yếu (top từ hay sai) và nhánh xu hướng theo tuần |
| "Một ngày có học" là gì | **Chỉ lượt ôn SRS** (`review_log`) | Streak không đụng `quiz_attempt` hay `vocab_entry`; quiz vẫn lên bảng số liệu nhưng không giữ streak |
| Mức chi tiết quiz | **Chỉ số liệu tổng hợp** | Không có bảng `quiz_session`, không migration, không sửa luồng generate/answer |
| Vị trí | **Tab thứ 5 "Thống kê"** | Không nhét vào tab Ôn tập |

## 4. Hợp đồng API

`GET /api/stats` — không tham số. Cửa sổ thời gian là hằng số phía server.

```jsonc
{
  "streak": { "current": 5, "longest": 23, "lastActiveDate": "2026-08-11" },
  "totals": { "reviews": 1284, "learnedWords": 312, "activeDays": 87 },
  "daily": [ { "date": "2026-05-13", "reviews": 0 }, /* … đúng 91 phần tử … */ ],
  "recall": { "again": 210, "hard": 180, "good": 640, "easy": 254 },
  "quiz": [
    { "type": "FILL_BLANK",         "attempts": 40, "correct": 31, "avgScore": null },
    { "type": "COLLOCATION_CHOICE", "attempts": 22, "correct": 18, "avgScore": null },
    { "type": "FREE_WRITE",         "attempts": 15, "correct":  9, "avgScore": 72   }
  ]
}
```

Bốn điều dưới đây là **hợp đồng**, không phải chi tiết cài đặt:

**`daily` luôn có đúng 91 phần tử, ngày không ôn mang `reviews: 0`.** Backend bơm đầy
khoảng trống. Trả mảng thưa rồi bắt client tự dựng lịch là đẩy phép tính ngày tháng sang
chỗ không có `settings.tz`.

**`avgScore` là `null` với `FILL_BLANK` và `COLLOCATION_CHOICE`.** Hai loại đó chấm 100
hoặc 0, nên điểm trung bình chỉ là `correct/attempts` viết lại bằng đơn vị khác. `null` ở
đây nghĩa là "loại này không có khái niệm điểm" — cùng ngữ nghĩa `improvedVersion` đã dùng
trong `AnswerResultDto`, không phải "chưa có dữ liệu".

**`quiz` luôn có đủ 3 phần tử theo thứ tự `FILL_BLANK`, `COLLOCATION_CHOICE`,
`FREE_WRITE`,** kể cả khi `attempts: 0`. Vắng hàng thì UI phải phân nhánh "chưa làm loại
này" ở ba chỗ.

**`recall` trả số lượt thô theo 4 mức, KHÔNG trả sẵn tỉ lệ.** Tỉ lệ nhớ là `1 − again/tổng`,
một phép chia ở client. Trả cả hai là dựng hai nguồn sự thật cho cùng một con số.

Mọi khoá luôn có mặt kể cả khi giá trị là `null` — mirror TypeScript khai `number | null`
chứ không phải optional.

### Phạm vi thời gian

`totals`, `recall`, `quiz` tính trên **toàn bộ lịch sử**. Chỉ `daily` giới hạn 91 ngày.

Chọn toàn bộ lịch sử vì đây là màn động lực: con số phải to lên mãi. Tỉ lệ tính trên cửa sổ
30 ngày nhảy loạn khi người dùng mới làm 3 câu quiz trong tháng, và đó đúng là lúc họ cần
được khích lệ nhất.

## 5. Backend

Package mới `api-service/app/stats/` theo đúng khuôn các feature package hiện có:
`models.py` (chỉ DTO, **không entity**), `repository.py`, `service.py`, `streak.py`,
`router.py`. Đăng ký router ở `app/main.py` sau `quiz_router`.

### 5.1 Ba câu truy vấn

| # | Câu | Nuôi |
|---|---|---|
| 1 | `review_log` GROUP BY ngày, **toàn bộ lịch sử** | `daily` (cắt 91 ngày cuối), `totals.reviews` (tổng), `totals.activeDays` (số dòng), `streak` |
| 2 | `review_log` GROUP BY rating | `recall` |
| 3 | `quiz_attempt` JOIN `quiz_item` GROUP BY type | `quiz` |

Câu 1 gom trên toàn bộ lịch sử chứ không chỉ 91 ngày, và một mình nó nuôi bốn con số. Số
dòng trả về bằng số **ngày** đã từng ôn — không phải số lượt — nên ba năm học đều là ≤1095
dòng. Tách thành hai câu riêng (một cho `daily`, một cho `streak`) là tạo cơ hội cho hai cửa
sổ lệch nhau vào lần đầu ai đó sửa hằng số 91.

`totals.learnedWords` dùng lại `srs.repository.count_learned` sẵn có (`repetitions >= 1`).
Viết lại câu đếm đó ở `stats/repository.py` là dựng định nghĩa thứ hai cho "đã học", và hai
định nghĩa đó sẽ trôi khỏi nhau.

### 5.2 Múi giờ — chỗ dễ hỏng nhất

Mọi phép gom theo ngày dùng `(reviewed_at AT TIME ZONE :tz)::date` với `:tz = settings.tz`
(`config.py:98`, mặc định `Asia/Ho_Chi_Minh`, đã tồn tại — **không thêm config mới**).

**Không được có `::date` trần ở bất kỳ đâu.** `reviewed_at` là `TIMESTAMPTZ`; cast trần quy
về UTC, nên lượt ôn 20:00 ngày 11/8 giờ Việt Nam rơi vào ô ngày 12/8 và streak đứt sai.
Không lỗi, không exception, không test nào đỏ trừ khi có test viết riêng cho nó (mục 7).

### 5.3 `stats/streak.py` — hàm thuần, tách riêng

Nhận `list[date]` đã sắp xếp cộng `today` bơm từ ngoài, trả `(current, longest,
last_active)`. Không chạm `Session`, không gọi `date.today()` bên trong.

Tách riêng vì cùng lý do `srs/scheduler.py` tách khỏi `srs/service.py`: logic ngày tháng là
chỗ off-by-one sống lâu nhất, và nó chỉ test được tử tế khi `today` là tham số.

**Quy tắc phải chốt rõ: hôm nay chưa ôn thì streak vẫn tính từ hôm qua.** Mở panel lúc 9
giờ sáng thấy streak về 0 là sai, và sai đúng lúc phản tác dụng nhất. Streak chỉ đứt khi
**cả hôm nay lẫn hôm qua** đều trống — đúng cách Anki và Duolingo làm.

Ca biên phải trả đúng: không ngày nào (`0, 0, None`); chỉ hôm nay (`1, 1`); chỉ hôm qua
(`1, 1`); đứt quãng 2 ngày; chuỗi dài nhất nằm ở quá khứ chứ không phải hiện tại.

### 5.4 Cách ly người dùng

Không bảng nào trong ba câu có cột `user_id` — chủ sở hữu nằm ở `vocab_entry.user_id`
(điều 13). Cả ba câu đi qua `review_log → srs_card → vocab_entry` hoặc
`quiz_attempt → quiz_item → vocab_entry` rồi lọc.

`GET /api/stats` **phải có mặt trong `tests/test_multi_user_isolation.py`**. Endpoint không
nằm trong file đó là endpoint chưa được chứng minh an toàn.

`stats/repository.py` cố ý đọc chéo cả ba context; docstring đầu file ghi rõ lý do: đây là
read model báo cáo, đọc ngang là việc của nó. Khác với `quiz/candidates.py` — file đó phải
khoanh vùng vì quiz chỉ chạm dữ liệu SRS ở đúng một chỗ và chỗ đó cần nhìn thấy bằng mắt.

### 5.5 Lỗi

Không thêm mã lỗi mới vào `common/errors.py`. Người dùng mới toanh **không phải là lỗi**:
endpoint trả `streak.current = 0`, `daily` gồm 91 ngày `reviews: 0`, `quiz` đủ 3 hàng
`attempts: 0`. `GET /api/stats` không bao giờ trả 404.

### 5.6 Không thêm index

Ba câu quét `review_log` của một người. Ở quy mô cá nhân đó là vài mili giây, và thêm index
đồng nghĩa với `V8` — thứ cả thiết kế này đang tránh. Nếu sau này chậm thật thì lúc đó đã có
số liệu để chọn đúng index; bây giờ thì chưa.

## 6. Extension

| Tệp | Việc |
|---|---|
| `shared/types.ts` | Gương DTO backend: `StatsDto`, `DailyPoint`, `RecallBreakdown`, `QuizTypeStats` |
| `shared/messages.ts` | `GetStatsRequest` → union `ExtensionRequest` → `ResponseMap` (điều 2) |
| `shared/heatmap.ts` + test | **mới** — dựng lưới, hàm thuần |
| `background/api-client.ts` | `getStats()` |
| `background/service-worker.ts` | nhánh `GET_STATS` |
| `sidepanel/StatsTab.tsx` + test | **mới** — nạp dữ liệu, trạng thái, bố cục |
| `sidepanel/StatsCharts.tsx` + test | **mới** — ba component vẽ thuần, chỉ nhận props |
| `sidepanel/App.tsx` | tab thứ 5 |
| `sidepanel/styles.css` | style biểu đồ |

Side panel không gọi HTTP (điều 1) — `StatsTab` gọi `sendToBackground({ type: 'GET_STATS' })`.

Tách `StatsCharts.tsx` khỏi `StatsTab.tsx` vì `QuizTab.tsx` đã phình tới 19.5K và lý do
chính là gộp nạp dữ liệu với vẽ vào một tệp. Component vẽ chỉ nhận props nên test bằng
fixture thẳng, không cần giả lập `sendToBackground`.

### 6.1 Biểu đồ viết tay, không thư viện

Điều 12 cấm thêm dependency. Không dùng Recharts, Chart.js, D3, và **cũng không dùng SVG**:

- Cột theo ngày = 30 `div` cao theo `%`
- Heatmap = CSS grid 7 hàng × 13–14 cột
- Thanh tỉ lệ = `div` lồng

Dùng lại `--accent` / `--surface` / `--surface-2` sẵn có nên tự hợp dark mode, và gắn
`aria-label` / `title` được tử tế — thứ SVG phải bù thêm.

### 6.2 `shared/heatmap.ts` — hai cái bẫy

**Bẫy 1: `new Date("2026-08-11")` là nửa đêm UTC.** Ở múi giờ âm, `.getDay()` trả về thứ của
ngày hôm trước, cả lưới lệch một ô và không có gì báo. Module này phải tự tách chuỗi rồi
dựng `new Date(2026, 7, 11)`. Đây chính là lý do nó là tệp riêng có test riêng thay vì vài
dòng nằm lẫn trong JSX.

**Bẫy 2: client không bao giờ tự tính "hôm nay".** Phần tử cuối của `daily` chính là hôm nay
theo `settings.tz` của server. Gọi `new Date()` ở client để suy ra hôm nay là mở lại đúng cái
lỗ múi giờ mà mục 5.2 vừa bịt.

Hàm trả các cột 7 ô (T2→CN), ô đệm đầu và cuối là `null`. 91 ngày cộng đệm ra 13–14 cột; ở
368px nội dung, ô ~16px với khe 3px là vừa, còn chỗ cho nhãn thứ bên trái.

### 6.3 Thang màu cố định

Năm mức theo số lượt ôn trong ngày: `0` / `1–4` / `5–14` / `15–29` / `30+`.

Cố ý **không** co theo giá trị lớn nhất. Thang co theo max làm tuần lười nhất trông y hệt
tháng chăm nhất — màu phải mang cùng một nghĩa vào tháng 1 và tháng 6, nếu không biểu đồ chỉ
còn là trang trí. Ngưỡng nằm trong module thuần nên test được.

### 6.4 Biểu đồ cột

30 phần tử cuối của `daily`. Chiều cao `count / max` với `max` là giá trị lớn nhất trong 30
ngày đó. Ngày 0 lượt vẫn vẽ mẩu 2px — cột biến mất và cột lùn là hai thông tin khác nhau.

### 6.5 Khả năng tiếp cận

Mỗi khối biểu đồ là một `role="img"` với `aria-label` tóm tắt (ví dụ "Lịch ôn 91 ngày gần
nhất: 47 ngày có ôn, cao nhất 32 lượt ngày 03/08"). Từng ô chỉ có `title` để rê chuột.

Nhãn nói "91 ngày" chứ không phải "13 tuần": lưới ra 13 hay 14 cột tuỳ hôm nay rơi vào thứ
mấy, nên "13 tuần" là con số sai vào phần lớn các ngày trong tuần.

Gắn `aria-label` cho cả 91 ô là bắt trình đọc màn hình đọc 91 câu để nói một điều mà hàng số
liệu phía trên đã nói rồi. Test RTL truy theo `role="img"` + tên, đúng quy ước "query theo
vai trò người dùng thấy".

### 6.6 Bốn trạng thái

1. Đang tải → `Đang tải…`
2. Lỗi → thông điệp + nút *Thử lại* khi `error.retryable`
3. `totals.reviews === 0` → lời nhắc ngắn thay vì bốn khối rỗng. Tường số 0 và heatmap trắng
   trơn không nói được gì cho người vừa cài
4. Có dữ liệu → bốn khối

Ba trạng thái đầu theo đúng khuôn `ReviewTab` hiện có.

### 6.7 Tab thứ 5

`.tabs button` hiện là `font-size: 13.5px; padding: 13px 8px 11px; flex: 1`. Năm tab ở 400px
cho mỗi tab ~72px, còn ~56px cho chữ — "Thống kê" sát mép. Dự kiến giảm padding ngang xuống
4px và font xuống 13px.

**Con số này phải đo trên bản build thật rồi mới chốt**, không suy từ CSS. Phương án lùi nếu
không vừa: đổi nhãn thành "Tiến độ".

### 6.8 Mẫu số bằng 0

Ba phép chia trong màn này chia cho 0 được, và `NaN%` chiều cao là cột không hiện — hỏng
lặng lẽ, không exception:

| Phép chia | Khi nào mẫu = 0 | Vẽ gì |
|---|---|---|
| `reviews / max` (cột theo ngày) | Có lượt ôn cũ nhưng **không lượt nào trong 30 ngày qua** — trạng thái rỗng ở 6.6 không bắt được ca này vì nó xét `totals.reviews` toàn thời gian | Mọi cột vẽ mẩu 2px, không tính tỉ lệ |
| `correct / attempts` (mỗi loại quiz) | Chưa làm loại đó bao giờ | Hiện `—`, **không phải `0%`** — chưa làm và làm sai hết là hai chuyện |
| `1 − again / tổng` (tỉ lệ nhớ) | Chưa ôn lượt nào | Không xảy ra khi đã qua trạng thái rỗng 6.6, nhưng vẫn phải trả `—` chứ không `NaN` |

Ba ca này nằm trong test của `StatsCharts.test.tsx`.

## 7. Test

### Backend

| Tệp | Nội dung |
|---|---|
| `test_stats_streak.py` | Hàm thuần, **không chạm DB**. Rỗng; chỉ hôm nay; chỉ hôm qua; đứt 2 ngày; chuỗi dài nhất ở quá khứ; một ngày duy nhất cách đây một năm |
| `test_stats_endpoint.py` | `daily` đúng 91 phần tử; ngày trống được bơm `0`; `avgScore` `null` với hai loại không có điểm; `quiz` luôn 3 hàng đúng thứ tự; user mới trả toàn 0 |
| `test_multi_user_isolation.py` | **Bắt buộc theo điều 13.** Lượt ôn và lượt quiz của người B không lọt vào bất kỳ con số nào của người A |

Một test đáng giá hơn cả: **lượt ôn lúc 20:00 giờ Việt Nam phải rơi vào ô ngày hôm đó, không
phải hôm sau.** Đó là lỗi duy nhất trong thiết kế này chạy đúng trên máy dev ở UTC+7 buổi
sáng và sai trên máy thật buổi tối, mà không có gì đỏ.

Tên tệp phải khớp `test_*.py` trong `tests/` — đặt sai tên là test bị bỏ qua im lặng.

### Extension

`heatmap.test.ts` là chỗ nặng nhất: căn thứ trong tuần, ô đệm đầu/cuối, ngưỡng thang màu, và
một test chốt rằng `"2026-08-11"` cho ra đúng thứ Ba **kể cả khi `TZ` của tiến trình test là
`America/New_York`** — ai đó viết lại bằng `new Date(iso)` thì test này phải đỏ.

`StatsCharts.test.tsx` bơm fixture props, kiểm số ô và `aria-label`. `StatsTab.test.tsx` phủ
bốn trạng thái mục 6.6. `App.test.tsx` sửa thêm ca tab thứ 5.

### Cổng nghiệm thu

```
cd api-service && uv run pytest && uv run mypy app && uv run ruff check .
cd extension   && npm test && npm run build
```

Cả bốn lệnh phải dán được output thật. Test xanh mà mypy hoặc build đỏ vẫn tính là hỏng.

## 8. Rủi ro

1. **Múi giờ.** Bịt ở hai tầng — `AT TIME ZONE :tz` phía SQL (5.2), cấm `new Date()` phía
   client (6.2) — và mỗi tầng có test riêng.
2. **Thanh 5 tab tràn** ở 400px. Đo trên bản build thật (6.7). Phương án lùi: nhãn "Tiến độ".
3. **Xung đột với việc đang dở.** Nhánh `feat/manual-text-input` đang có `styles.css` sửa 812
   dòng chưa commit, mà tính năng này cũng thêm style vào đúng tệp đó. Nên commit hoặc chốt
   phần đang dở trước khi bắt đầu.

## 9. Cố ý không làm

Nêu ra để sau này không ai tưởng là bỏ sót:

- **Nhóm lượt quiz thành "một bài"** — đã chốt chỉ lấy số liệu tổng hợp. Việc này cần `V8`
  thêm `quiz_session` và sửa cả luồng generate lẫn answer.
- **Lưu thời gian làm mỗi câu** — hiện `ReviewTab` chỉ dùng để suy ra rating rồi bỏ.
- **Danh sách lịch sử từng câu đã làm** kèm nhận xét AI.
- **Chẩn đoán điểm yếu** — top từ hay sai, `lapses` cao. Đây là hướng riêng, đã loại lúc
  chọn mục đích.
- Bộ chọn khoảng thời gian, mục tiêu hằng ngày, xuất CSV thống kê.
- **Bảng rollup, index mới, migration.** Không có `V8` nào trong thiết kế này.
