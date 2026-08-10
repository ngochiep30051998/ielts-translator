# Nhập text thủ công để dịch

**Ngày:** 2026-08-07
**Trạng thái:** Design đã duyệt
**Phạm vi:** chỉ `extension/`. Backend không đổi, hợp đồng HTTP không đổi.

---

## 1. Vấn đề

Chỉ có đúng một đường vào tính năng dịch: bôi đen text có sẵn trên trang. Không dịch được
từ nghe thấy, từ trong ảnh, từ đang gõ dở, hay đoạn muốn sửa lại trước khi tra (bôi trúng
`was resiliented` nhưng thật ra muốn tra `resilient`).

## 2. Hành vi mới

Thêm ô nhập vào **tab "Dịch" của side panel**, ngay trên vùng kết quả.

```
┌────────────────────────────────┐
│ ┌────────────────────────────┐ │
│ │ Nhập hoặc dán text để dịch…│ │  textarea 3 dòng
│ └────────────────────────────┘ │
│ 0/1500              [ Dịch ]   │
├────────────────────────────────┤
│ resilient  /rɪˈzɪliənt/  ADJ   │  PayloadView — không đổi
│ …                              │
│              [Lưu từ] từ cache │
└────────────────────────────────┘
```

**Một vùng kết quả duy nhất.** Dịch từ ô nhập đè lên kết quả đang hiện, dù kết quả đó đến
từ bôi đen hay từ lần nhập trước. Không có khái niệm "kết quả bôi đen" tách khỏi "kết quả
nhập tay".

**Ô nhập tự điền `sourceText` của kết quả gần nhất** khi mở panel. Đó là cả lý do tính năng
này hữu ích nhất: bôi đen sai một chút thì sửa lại trong ô rồi dịch lại, không phải gõ từ
đầu.

Tự điền xảy ra **đúng một lần cho mỗi lần mở panel**, và chỉ khi có `lastResult`; không có
thì ô để trống. Dịch xong không đụng vào nội dung ô — text người dùng vừa gõ ở nguyên đó
để họ sửa tiếp.

Chi tiết tương tác:

- Nút `Dịch` disabled khi: trim rỗng, hoặc quá 1500 ký tự, hoặc đang dịch (nhãn đổi thành
  `Đang dịch…`).
- `Ctrl/Cmd+Enter` trong textarea = bấm `Dịch`. `Enter` vẫn xuống dòng.
- Đang dịch giữ nguyên kết quả cũ trên màn hình, không nháy trắng.
- Bộ đếm `n/1500` chuyển đỏ khi vượt.
- Empty state đổi từ `Bôi đen một đoạn text trên trang web để bắt đầu.` thành
  `Bôi đen text trên trang, hoặc nhập vào ô trên rồi bấm Dịch.`

## 3. Luồng dữ liệu

```
TranslateTab (textarea)
  → sendToBackground({ type: 'TRANSLATE_TEXT', text })
  → service-worker: client.translate({ text, contextSentence: null,
                                       sourceUrl: '', pageTitle: '' })
  → lastResult = result          (dùng chung với đường bôi đen)
  → App.setResult(result)
```

### Quyết định: message riêng, không dùng lại `TRANSLATE_SELECTION`

Thêm vào `shared/messages.ts`:

```ts
export interface TranslateTextRequest {
  type: 'TRANSLATE_TEXT';
  text: string;
}
```

cộng một nhánh trong union `ExtensionRequest` và `TRANSLATE_TEXT: TranslateResult` trong
`ResponseMap`.

Dùng lại `TRANSLATE_SELECTION` với `contextSentence: null, sourceUrl: '', pageTitle: ''`
sẽ chạy đúng và tốn 0 dòng hợp đồng, nhưng tên message thành nói dối và ràng buộc #2 nói
rõ luồng mới thì thêm message mới. Đổi tên `TRANSLATE_SELECTION` thành tên chung với các
field optional thì phải chạm content script và bộ test đang xanh — rủi ro không tương xứng.

Service worker xử lý `TRANSLATE_TEXT` bằng cách gọi đúng `client.translate` đang có, không
thêm method mới trong `ApiClient`.

## 4. Quyết định: nâng state lên `App`

`App` giữ `draft`, `result`, `loaded`; `TranslateTab` nhận qua props và thành component
thuần hiển thị.

Lý do: đổi sang tab "Sổ từ" rồi quay lại làm React unmount `TranslateTab`, mất sạch text
đang gõ dở. Nâng state lên `App` giữ nó sống suốt lần mở panel.

**Effect `GET_LAST_RESULT` phải chuyển lên `App` cùng lúc.** Để nguyên trong `TranslateTab`
thì mỗi lần quay lại tab nó chạy lại và ghi đè đúng cái draft vừa cố giữ — nâng state lên
mà không chuyển effect thì không sửa được gì.

Đóng hẳn side panel vẫn mất nháp; chấp nhận. Lưu nháp vào `chrome.storage.local` là bước
sau nếu thấy thiếu thật, không làm trước.

## 5. Quyết định: chuyển `validateSelection` sang `shared/`

`validateSelection()` và hằng `MAX_SELECTION_LENGTH` chuyển từ `content/selection.ts` sang
`shared/text.ts`. `extractContextSentence()` **ở lại** `content/selection.ts` — nó chỉ có
nghĩa với một DOM selection.

Side panel cần đúng logic chặn 1500 ký tự đó. Ba lựa chọn và lý do loại hai:

- Chép hằng số sang side panel → giới hạn 1500 tồn tại ở ba chỗ, vi phạm ràng buộc #9.
- `sidepanel/` import thẳng từ `content/` → chạy được nhưng dựng một phụ thuộc ngược giữa
  hai surface; `shared/` tồn tại đúng để tránh việc đó.

Kèm theo: sửa dòng tương ứng trong CLAUDE.md ràng buộc #9 (`content/selection.ts` →
`shared/text.ts`) và chuyển các ca test của `validateSelection` sang `shared/text.test.ts`.

Chặn 1500 phía client là để không đốt một vòng mạng cho thứ backend chắc chắn từ chối —
không thay thế chặn phía backend.

## 6. Lỗi

Giữ nguyên hình dạng `{ code, message, retryable }` (ràng buộc #4). Hiện
`<p className="status bad">{message}</p>` dưới nút `Dịch`, kèm nút `Thử lại` khi
`retryable` — bấm gửi lại đúng text đó, không đọc lại textarea (người dùng có thể đã sửa).

Lỗi không retryable (`TEXT_TOO_LONG`, `PARSE_ERROR`) chỉ hiện thông điệp, không có
`Thử lại`.

## 7. Backend: không đổi

`TranslateRequest` đã có `text` `@NotBlank` và ba field còn lại optional. Không migration,
không sửa prompt, không bump `version:`, không thêm quyền manifest.

Hai hệ quả cần biết trước:

- Text nhập tay không có context → **cache key khác** với cùng đoạn đó bôi đen trên trang
  (context nằm trong key). Đúng thiết kế cache; không xử lý gì.
- `sourceUrl: ''` → `api-client` đổi thành `undefined` → `buildVocabPayload` lưu
  `sourceUrl: null`. Từ nhập tay lưu vào sổ vẫn hợp lệ, chỉ là không có nguồn.
- `Mode.of` vẫn tự suy WORD/SENTENCE theo số token, nên nhập một từ vẫn ra payload WORD.
  Không cần người dùng chọn chế độ.

## 8. Test

| File | Ca |
|---|---|
| `shared/text.test.ts` | các ca `validateSelection` chuyển từ `content/selection.test.ts` sang |
| `TranslateTab.test.tsx` | nhập → bấm Dịch → gửi đúng một `TRANSLATE_TEXT`, text đã trim |
| | ô trống → nút disabled, **không** message nào được gửi |
| | 1501 ký tự → bộ đếm đỏ, nút disabled, **không** gửi message |
| | `Ctrl+Enter` gửi giống bấm nút |
| | lỗi `retryable` → hiện `Thử lại`, bấm gửi lại đúng text cũ |
| `App.test.tsx` (mới) | có `lastResult` → textarea điền sẵn `sourceText` |
| | gõ text mới → sang tab Sổ từ → quay lại: draft còn nguyên |
| `service-worker.test.ts` | `TRANSLATE_TEXT` gọi `client.translate` với `contextSentence: null`, cập nhật `lastResult` |

Hai ca khoá quyết định, thiếu thì lần refactor sau hỏng im lặng:

- **1501 ký tự không gửi message** — khoá mục 5. Không có nó thì ai đó bỏ nhánh validate
  ở side panel mà không gì đỏ, và giới hạn client biến mất.
- **Đổi tab draft còn nguyên** — khoá mục 4. Không có nó thì ai đó đẩy state ngược xuống
  `TranslateTab` cho "gọn" và nháp lại bốc hơi mỗi lần chuyển tab.

Chạy cả `npm test` **và** `npm run build` trước khi báo xong — build là nơi duy nhất chạy
type check, và thay đổi này chạm union `ExtensionRequest` nên type check là lưới bắt lỗi
chính.

## 9. Ngoài phạm vi

- Không đổi backend, không đổi prompt, không thêm quyền manifest.
- Không thêm ô "câu ngữ cảnh" riêng — muốn ngữ cảnh thì dán cả câu.
- Không lưu lịch sử các lần dịch tay.
- Không lưu nháp qua lần đóng panel.
- Không sửa khoảng trống sẵn có: panel đang mở mà bôi đen trên trang thì panel không tự
  cập nhật. Tự điền làm nó dễ thấy hơn, nhưng đó là bug riêng, tách ra việc khác.
