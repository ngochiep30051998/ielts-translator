# Bôi đen hiện icon, bấm icon mới dịch

**Ngày:** 2026-08-06
**Trạng thái:** Design đã duyệt
**Phạm vi:** chỉ `extension/`. Backend không đổi, hợp đồng API không đổi.

---

## 1. Vấn đề

Chế độ `auto` hiện dịch ngay khi bôi đen xong (debounce 250ms). Mỗi lần bôi đen là một
lượt gọi Gemini, kể cả khi người dùng chỉ đang chọn text để copy hoặc đọc lại. Tốn quota
cho thao tác không có ý định tra nghĩa, và bubble tự nhảy ra che nội dung trang.

## 2. Hành vi mới

Bôi đen xong chỉ hiện **một icon nhỏ**. Bấm icon mới gọi dịch.

```
mouseup ──250ms──▶ validate
                    ├─ quá dài  ──▶ bubble lỗi (như cũ)
                    ├─ rỗng     ──▶ ẩn
                    └─ hợp lệ   ──▶ chụp snapshot ──▶ [icon]
                                                       │ click
                                                       ▼
                                              Đang dịch… ──▶ kết quả
Alt+T ──────────────────────────────────────▶ Đang dịch… ──▶ kết quả
```

`Alt+T` **không** đi qua icon — bấm phím tắt đã là ý định rõ ràng.

Validate **trước** khi hiện icon. Hiện icon rồi mới báo "đoạn quá dài" là bắt người dùng
bấm một lần vô ích.

## 3. Quyết định: chụp dữ liệu lúc hiện icon

**`mousedown` lên một nút sẽ collapse selection của trang trước khi `click` kịp chạy.**
Nên handler click của icon **không được** đọc `window.getSelection()` — lúc đó nó có thể
đã rỗng.

Khi selection hợp lệ, chụp `{ text, contextSentence, rect }` vào một biến module rồi mới
hiện icon. Handler click dùng ảnh chụp. Thêm `preventDefault()` trên `mousedown` của icon
để vùng bôi đen không mất highlight trên màn hình.

Điều này sửa luôn một bug tiềm ẩn đang có: nút "Thử lại" hiện gọi
`translateCurrentSelection()` đọc lại `window.getSelection()`, nhưng lúc đó người dùng có
thể đã bấm đi chỗ khác — selection rỗng và retry **im lặng không làm gì**. Sau thay đổi,
retry dùng cùng ảnh chụp nên luôn dịch lại đúng đoạn cũ.

## 4. Icon dùng chung Shadow DOM host với bubble

Thêm `showIconBubble(rect, onClick)` vào `content/bubble.ts`, **không** tạo module riêng.

Lý do: `mountShadow()` đã tự xoá host cũ trước khi dựng cái mới, nên icon → loading →
kết quả thay thế nhau tự nhiên. `hideBubble()` và listener `mousedown`-ra-ngoài đã có sẵn
và chạy đúng luôn cho icon. CSS nằm một chỗ (`bubble.css.ts`).

## 5. Options

Nhãn chế độ `auto` đổi từ "Tự hiện bubble" thành "Hiện icon khi bôi đen".

**Giá trị lưu trong storage giữ nguyên `'auto'`** — không migration, không đụng
`normalise()` trong `shared/settings.ts`.

## 6. Test

| Ca | Khẳng định |
|---|---|
| Bôi đen hợp lệ | Chỉ có icon. **Không** message `TRANSLATE_SELECTION` nào được gửi |
| Bấm icon | Gửi đúng một `TRANSLATE_SELECTION` với text đã chụp |
| Selection bị xoá sau khi hiện icon, rồi mới bấm | Vẫn gửi đúng text — chứng minh dùng ảnh chụp, không đọc lại DOM |
| Bôi đen quá dài | Ra bubble lỗi, **không** ra icon |
| Bôi đen rỗng | Ẩn hết |
| `Alt+T` | Dịch thẳng, không qua icon |

Ca thứ nhất là test quan trọng nhất: nó khoá đúng mục tiêu của thay đổi này — chỉ bôi đen
thì không tốn quota. Thiếu nó thì lần refactor sau ai đó gọi lại `translate` trong nhánh
`auto` mà không gì đỏ.

Ca thứ ba là ca duy nhất chứng minh được quyết định mục 3; không có nó thì cách đọc
`window.getSelection()` lúc click vẫn xanh trong test (jsdom không tự collapse selection)
rồi hỏng trên trình duyệt thật.

## 7. Ngoài phạm vi

- Không đổi backend, không đổi hợp đồng API, không thêm quyền trong manifest.
- Không thêm chế độ thứ ba — `auto` và `hotkey` giữ nguyên hai giá trị.
- Không đổi nội dung bubble kết quả, không đổi luồng lưu từ.
