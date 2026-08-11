# Bỏ giới hạn "một ngày một lần" ở tính năng ôn tập

**Ngày:** 2026-08-11
**Trạng thái:** Design đã duyệt
**Phạm vi:** `api-service/` + `extension/`. Một migration (`V8`), hai endpoint mới, một field
mới trong hợp đồng thống kê.

---

## 1. Vấn đề

Ôn hết hàng đợi là tab Ôn tập báo "Hôm nay không còn thẻ nào đến hạn" và không còn gì để
làm. Muốn học thêm cũng không được, muốn gặp lại từ vừa quên cũng phải đợi sang mai.

Ba cơ chế độc lập cùng tạo ra cảm giác đó, nằm ở ba tệp khác nhau:

| Cơ chế | Ở đâu | Hệ quả |
|---|---|---|
| Sàn interval 1 ngày | `srs/scheduler.py` — `_at_least_one_day`, và `AGAIN` luôn trả `interval = 1` | Ôn xong một thẻ thì hôm nay không gặp lại nó nữa, kể cả khi bấm "Lại" vì quên |
| Hàng đợi lọc `due_date <= today` | `srs/repository.py:71` | Hết hàng đợi là hết bài |
| Hạn mức từ mới mỗi ngày | `srs/service.py:_remaining_new_today` + ô "Từ mới mỗi ngày" ở Options (mặc định 30) | Mỗi ngày chỉ được 30 từ mới |

## 2. Ràng buộc không được phá

**Ôn thêm KHÔNG được đụng lịch SM-2.** Mỗi lượt qua `POST /api/srs/review` tăng
`repetitions` và nhân `interval` với `ease_factor`. Ôn một thẻ 5 lần trong ngày ở mức "Nhớ"
đẩy interval 1 → 6 → 15 → 37 → 92 ngày. Càng chăm ôn, thẻ càng bị đẩy xa — đúng ngược điều
người dùng muốn.

Đây là ràng buộc trung tâm. Mọi quyết định dưới đây phục vụ nó.

**Hệ quả: `srs/scheduler.py` KHÔNG bị sửa một dòng nào.** Sàn interval 1 ngày và `AGAIN → 1`
ở §1 vẫn giữ nguyên — chúng đúng, và chúng là thứ làm SM-2 hoạt động. Cái được gỡ là **hệ quả
nhìn thấy** của chúng ở tầng trên: hàng đợi không còn chặn, và thẻ vừa quên hiện lại trong
buổi qua hàng đợi cục bộ của panel (§8.2). Ai đọc spec này rồi mở `scheduler.py` ra sửa là đã
hiểu ngược.

## 3. Quyết định phạm vi

Chốt lúc brainstorm, ghi lại vì mỗi cái loại bỏ một nhánh việc lớn:

| Câu hỏi | Chốt | Hệ quả |
|---|---|---|
| Bỏ giới hạn nào | **Cả ba** | Ba nhánh việc độc lập, ghép trong một spec |
| Lượt ôn thêm có tính vào lịch SRS | **Không — luyện tập tự do** | Cần tách hai khái niệm ở cả DB, API lẫn UI |
| Có ghi vào `review_log` | **Có, đánh dấu riêng** | Cần `V8` thêm cột; thống kê phải phân biệt |
| Bấm "Lại" hiện lại trong buổi | **Hàng đợi phía panel** | Không đổi `due_date` sang `TIMESTAMPTZ`, không đụng backend |
| Hạn mức từ mới | **`0` = không giới hạn** | Một dòng ở service, một nhãn ở Options |

## 4. Mô hình dữ liệu

### 4.1 Migration

```sql
-- V8__review_log_mode.sql
ALTER TABLE review_log ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'SCHEDULED';
```

`DEFAULT 'SCHEDULED'` không phải cho tiện: **mọi dòng đang có đều đúng là lượt ôn theo lịch**,
nên default đó backfill chính xác toàn bộ lịch sử mà không cần câu `UPDATE` nào. Thống kê cũ
không đổi một con số.

Theo ràng buộc #15, migration **không** chạy lúc cold start trên Vercel — phải chạy tay một
lần trên Supabase.

### 4.2 Enum

```python
class ReviewMode(enum.StrEnum):
    SCHEDULED = "SCHEDULED"   # lượt ôn theo lịch — ĐỔI due_date, interval, ease_factor
    PRACTICE  = "PRACTICE"    # luyện thêm — KHÔNG đụng gì tới lịch
```

## 5. Hợp đồng API

Hai endpoint mới, **tách hẳn** khỏi `/api/srs/review`:

```
GET  /api/srs/practice?limit=N   → list[CardDto]   (dùng lại CardDto sẵn có)
POST /api/srs/practice           → { cardId, rating } → 204 No Content
```

Tách chứ không thêm field `mode` vào `POST /api/srs/review`, vì hai lý do:

**Kiểu trả về khác nhau về bản chất.** `ReviewResponse` mang `nextDueDate`, `intervalDays`,
`easeFactor` — luyện thêm không có ba thứ đó. Nhồi chung một endpoint buộc phải trả số giả
cho nửa số lượt gọi, và số giả trong response là thứ sẽ có người tin.

**Nhầm mode là hỏng im lặng.** Gửi `PRACTICE` cho một lượt ôn thật thì lịch đứng yên mãi
mãi; gửi `SCHEDULED` cho luyện tập thì interval phình đúng như §2 cảnh báo. Hai đường riêng
làm chỗ rẽ nhìn thấy được ở tầng routing, không nằm trong một `if` giữa service.

### 5.1 Hàng đợi luyện thêm

Thẻ có `repetitions >= 1`, xáo ngẫu nhiên, cắt ở `limit`. Tức là "mọi từ đã học ít nhất một
lần".

Thẻ `NEW` **không** vào: lượt đầu đời của một thẻ phải đi đường có lịch, nếu không nó mắc kẹt
ở trạng thái `NEW` vĩnh viễn.

Thẻ đang đến hạn **vẫn** nằm trong hàng luyện, nên một từ có thể xuất hiện ở cả hai chế độ
trong cùng ngày. Cố ý không loại: luật "mọi từ đã học" giải thích được bằng một câu, còn
"mọi từ đã học trừ những từ đến hạn hôm nay" thì không — và luyện một thẻ đang đến hạn không
làm nó biến mất khỏi hàng ôn thật, đúng như nó phải thế.

Hàng luyện dùng lại `_load_fresh_distractors` và `_request_missing` của `due()`. Bỏ qua sẽ
làm chế độ luyện im lặng không dùng được với từ chưa sinh mồi nhử.

## 6. Backend

| Tệp | Việc |
|---|---|
| `migrations/V8__review_log_mode.sql` | **mới** |
| `srs/models.py` | `ReviewMode`, cột `ReviewLog.mode`, DTO `PracticeRequest` |
| `srs/repository.py` | `find_practice_cards`; `insert_review_log` nhận thêm `mode`; `count_introduced_since` lọc mode |
| `srs/service.py` | `practice()`; gom hạn mức từ mới vào `_new_room` |
| `srs/router.py` | hai route mới |
| `tests/test_multi_user_isolation.py` | hai endpoint mới (ràng buộc #13) |

### 6.1 `practice()` — điều quan trọng nhất là thứ nó KHÔNG làm

```python
def practice(db: Session, user_id: int, card_id: int, rating: Rating) -> None:
    card = repo.find_owned_card(db, card_id, user_id)
    if card is None:
        raise AppError.of(ErrorCode.NOT_FOUND, f"Không tìm thấy thẻ id={card_id}")

    # KHÔNG gọi next_schedule, KHÔNG gán lại card.*. Đó là toàn bộ điểm khác biệt giữa hàm
    # này và review(). Thêm một dòng chạm `card` ở đây là làm hỏng đúng thứ chế độ luyện
    # thêm sinh ra để bảo vệ.
    repo.insert_review_log(
        db, card_id=card.id, rating=rating,
        prev_interval=card.interval_days, new_interval=card.interval_days,
        mode=ReviewMode.PRACTICE,
    )
```

`prev_interval` và `new_interval` cùng bằng interval hiện tại. Không phải số giả — lịch thật
sự không đổi, nên hai con số đó thật sự bằng nhau.

### 6.2 `insert_review_log` nhận `mode` BẮT BUỘC, không default

Đặt default `SCHEDULED` cho tiện nghĩa là mọi người gọi sau này mặc nhiên ghi lượt ôn theo
lịch mà không hề chọn — và ghi nhầm loại ở đây không làm gì đỏ, nó chỉ lặng lẽ làm sai streak
và tỉ lệ nhớ. Bắt buộc thì `mypy` ép từng chỗ gọi phải quyết định.

### 6.3 Hạn mức từ mới

```python
def _new_room(db: Session, user_id: int, new_limit: int, cap: int) -> int:
    """Số thẻ MỚI còn được nhận hôm nay, đã kẹp trong `cap`.

    `new_limit = 0` nghĩa là KHÔNG giới hạn — đó là cách người dùng tắt hẳn hạn mức từ ô
    "Từ mới mỗi ngày" ở Options.
    """
    if new_limit <= 0:
        return max(0, cap)
    return max(0, min(cap, new_limit - _introduced_today(db, user_id)))
```

Hiện `due()` và `stats()` tự ghép `min()` theo hai cách hơi khác nhau; gộp lại để "0 nghĩa là
không giới hạn" chỉ tồn tại ở đúng một chỗ.

### 6.4 `count_introduced_since` phải lọc `mode = 'SCHEDULED'`

Hàm này nhận diện lượt đầu đời của thẻ bằng `prev_interval == 0`. Hàng luyện chỉ chứa thẻ
`repetitions >= 1` nên hôm nay không dòng `PRACTICE` nào có `prev_interval = 0` — nhưng bất
biến đó phụ thuộc vào định nghĩa hàng luyện, thứ có thể đổi. Thêm một mệnh đề `WHERE` làm nó
không phụ thuộc nữa.

### 6.5 Cách ly người dùng

`find_practice_cards` join `vocab_entry` rồi lọc `user_id`. `POST /api/srs/practice` tra thẻ
theo `(id, user_id)` và trả `NOT_FOUND` chứ không `FORBIDDEN`.

Cả hai endpoint phải có mặt trong `test_multi_user_isolation.py`. Ca đáng giá nhất: **luyện
thẻ của người khác trả 404 VÀ `review_log` không có dòng nào mới** — kiểm cả status lẫn dữ
liệu, vì trả 404 mà vẫn ghi log là ca tệ nhất và im lặng nhất.

## 7. Va chạm với tab Thống kê

Lựa chọn "streak chỉ tính lượt đến hạn, biểu đồ ngày tính cả hai" tạo ra một mâu thuẫn nhìn
thấy được: **có ngày ô heatmap tô đậm mà streak vẫn đứt.** Người dùng sẽ nghĩ phần mềm hỏng.

Cách chữa: làm sự khác biệt đó nói ra được **ngay tại chỗ gây nhầm** — trong `title` của ô.

**Nguyên tắc: không field nào đang có bị đổi nghĩa.** Thêm đúng một field mới:

```jsonc
"daily": [ { "date": "2026-08-11", "reviews": 12, "practice": 5 } ]
```

| Con số | Đếm gì | Vì sao |
|---|---|---|
| `streak`, `recall`, `totals.*` | chỉ `SCHEDULED` | Giữ nguyên nghĩa cũ. Streak đo kỷ luật theo lịch; tỉ lệ nhớ trộn hai loại hoạt động thì không so sánh được với chính nó tháng trước |
| `daily[].reviews` | chỉ `SCHEDULED` | Giữ nguyên nghĩa cũ |
| `daily[].practice` | chỉ `PRACTICE` | Field mới, mang thông tin mới |
| Chiều cao cột, độ đậm ô | `reviews + practice` | Công sức là công sức |
| `title` của ô | `"11/08: 12 lượt ôn · 5 lượt luyện thêm"` | Chỗ duy nhất mâu thuẫn kia giải thích được |

**Mọi test thống kê hiện có phải xanh nguyên sau thay đổi này.** Test cũ đỏ nghĩa là đã đổi
nghĩa một field đang có chứ không phải thêm field mới — đó là tín hiệu dừng lại, không phải
test cần sửa.

### 7.1 Cái bẫy trong `dem_luot_on_theo_ngay` — đọc trước khi sửa hàm này

Hàm đó hiện trả `list[(ngày, số lượt)]` và **một mình nó nuôi bốn con số**: `daily`,
`totals.reviews`, `totals.activeDays` (= `len()` của danh sách), và `streak` (= các `ngày`
trong danh sách).

Thêm cột đếm `PRACTICE` vào đúng câu đó thì `GROUP BY` sẽ bắt đầu trả về **cả những ngày chỉ
có lượt luyện**. Hậu quả dây chuyền, không có gì đỏ:

- `len(theo_ngay)` tăng → `totals.activeDays` lặng lẽ đổi nghĩa thành "ngày có bất kỳ hoạt
  động nào"
- danh sách ngày dài ra → **`streak` bắt đầu tính cả ngày chỉ luyện**, phá thẳng quy tắc ở
  bảng trên và phá luôn lựa chọn "streak chỉ tính lượt đến hạn"

Nói cách khác: chỉ cần thêm một cột `SELECT`, streak đổi hành vi mà không ai chạm vào
`streak.py`.

**Bắt buộc:** `streak` và `totals.activeDays` phải lọc theo `scheduled > 0`, không phải theo
sự tồn tại của dòng. Và phải có một test chốt riêng: **một ngày CHỈ có lượt `PRACTICE` không
được giữ streak và không được tính vào `activeDays`.**

Ba chỗ sửa: `stats/repository.py` (câu gom theo ngày trả thêm cột đếm `PRACTICE`; hai câu còn
lại thêm `WHERE mode = 'SCHEDULED'`), `stats/models.py` + `shared/types.ts` (field `practice`),
`StatsCharts.tsx` (cộng hai số cho chiều cao, tách hai số trong `title`).

## 8. Extension

**Chỗ đặt "Luyện thêm" đã bị quyết sẵn bởi phép đo ở spec trước:** thanh tab ở 400px chỉ còn
thừa 6.2px với 5 tab. **Không có tab thứ 6.** Chế độ luyện sống bên trong tab Ôn tập.

| Tệp | Việc |
|---|---|
| `shared/types.ts` | `DailyPoint.practice` |
| `shared/messages.ts` | `GET_PRACTICE_CARDS`, `SUBMIT_PRACTICE` (đủ 4 bước hợp đồng, ràng buộc #2) |
| `background/api-client.ts` | `getPracticeCards`, `submitPractice` |
| `background/service-worker.ts` | hai nhánh; **`SUBMIT_PRACTICE` KHÔNG gọi `refreshBadge`** |
| `sidepanel/ReviewTab.tsx` | chế độ + hàng đợi học lại |
| `sidepanel/StatsCharts.tsx` | cộng hai số cho chiều cao, tách trong `title` |
| `options/Options.tsx` | nhãn thành "Từ mới mỗi ngày (0 = không giới hạn)" |

`SUBMIT_PRACTICE` không đụng badge vì lịch không đổi, nên số thẻ đến hạn không thể đổi — cùng
lý do `GET_STATS` không đụng badge.

### 8.1 Luồng

Tab Ôn tập mặc định ở chế độ theo lịch. Hết hàng đợi thì trạng thái rỗng hiện thêm nút
**Luyện thêm**.

Ở chế độ luyện, phía trên xấp thẻ có một dòng nói rõ **"Luyện thêm — không ảnh hưởng lịch
ôn"** kèm nút quay lại. Dòng đó bắt buộc: không có nó, người dùng trả lời hai chục thẻ rồi
thấy badge không giảm và kết luận phần mềm hỏng.

### 8.2 Hàng đợi học lại — quy tắc quan trọng nhất

> Mỗi thẻ đóng góp **nhiều nhất một** lượt `SCHEDULED` trong một buổi.
> Mọi lần hiện lại đều là `PRACTICE`.

Trả lời sai thì thẻ được chèn lại vào xấp, cách vị trí hiện tại vài thẻ (hết xấp thì nối vào
cuối). Lượt trả lời **đầu tiên** đã gửi `SUBMIT_REVIEW` và đã kéo lịch về gần — đúng, đó là
một lần quên. Lượt thứ hai trong cùng buổi gửi `SUBMIT_PRACTICE`.

Nếu lượt thứ hai cũng gửi `SUBMIT_REVIEW`, nó tính tiếp từ trạng thái vừa lapse và đẩy
interval lên lại — tức là **trả lời đúng ở lần thứ hai xoá mất dấu vết đã quên**. Đó chính là
lỗi §2 mô tả, chỉ khác là xảy ra trong phạm vi một buổi thay vì một ngày.

Quy tắc áp dụng cho cả hai chế độ.

## 9. Test

### Backend

| Tệp | Nội dung |
|---|---|
| `test_srs_practice.py` (mới) | `practice()` KHÔNG đổi `due_date`/`interval_days`/`ease_factor`/`repetitions`/`state`; ghi đúng một dòng `mode = 'PRACTICE'`; hàng luyện loại thẻ `NEW`; thẻ lạ trả 404 |
| `test_srs_service.py` / hiện có | `new_limit = 0` cho ra không giới hạn; `new_limit = 5` vẫn chặn ở 5 |
| `test_stats_*.py` hiện có | **phải xanh nguyên, không sửa một dòng** |
| `test_stats_endpoint.py` | thêm ca: lượt `PRACTICE` vào `daily[].practice`, KHÔNG vào `streak`/`recall`/`totals` |
| `test_multi_user_isolation.py` | `GET`/`POST /api/srs/practice` (ràng buộc #13) |

Ca đáng giá nhất phía backend: **luyện một thẻ 5 lần rồi khẳng định `srs_card` không đổi một
cột nào.** Đó là bất biến trung tâm của cả spec; mọi thứ khác hỏng thì còn sửa được, cột đó
đổi là lịch học của người dùng hỏng vĩnh viễn.

### Extension

Ca đáng giá nhất: **trả lời sai rồi trả lời đúng phải sinh đúng một `SUBMIT_REVIEW` và đúng
một `SUBMIT_PRACTICE`, theo đúng thứ tự đó.** Đây là quy tắc §8.2, và nó chỉ test được bằng
cách đếm message gửi đi.

Kèm: thẻ trả lời sai có hiện lại trong xấp không; chế độ luyện có hiện dòng cảnh báo không;
nút Luyện thêm chỉ hiện ở trạng thái rỗng.

### Cổng nghiệm thu

```
cd api-service && uv run pytest && uv run mypy app && uv run ruff check .
cd extension   && npm test && npm run build
```

## 10. Rủi ro

1. **Nhầm hai đường ghi log.** Bịt bằng hai endpoint tách rời và `mode` bắt buộc không
   default. Test "luyện 5 lần, `srs_card` không đổi" là chốt chặn cuối.
2. **Học 300 từ mới trong một ngày = 300 thẻ cùng đến hạn ngày mai.** Hạn mức không phải để
   làm khó; nó giữ cho ngày mai còn ôn nổi. `0` = không giới hạn trao quyền đó cho người dùng
   thay vì gỡ phanh vĩnh viễn — nhưng người bật `0` cần biết mình đang đánh đổi gì.
3. **Migration phải chạy tay trên Supabase** (ràng buộc #15). Quên thì mọi lượt ôn chết vì
   cột `mode` không tồn tại.

## 11. Cố ý không làm

- **Lịch trong ngày ở backend** (`due_date` → `TIMESTAMPTZ`). Panel tự làm được bằng hàng đợi
  cục bộ; đổi kiểu cột kéo theo mọi truy vấn SRS, mọi test, và badge.
- **Xoá hẳn ô "Từ mới mỗi ngày".** Phải bỏ tham số `newLimit` khỏi API và sửa cả chuỗi
  settings — nhiều việc hơn để có ít lựa chọn hơn.
- **Thống kê riêng cho chế độ luyện** (streak luyện, biểu đồ luyện). `daily[].practice` đã đủ
  để vẽ; màn thống kê riêng là tính năng khác.
- **Chọn bộ từ để luyện** (theo tag, theo độ khó, theo `lapses`). Hàng luyện hiện là xáo ngẫu
  nhiên toàn bộ từ đã học. Lọc là hướng riêng, đáng làm sau khi biết người dùng thật sự luyện
  thế nào.
