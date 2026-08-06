---
name: team
description: Điều phối team 5 vai cho ielts-translator — pm, senior-ba, techlead, senior-backend, senior-frontend. Dùng khi một việc cần nhiều vai phối hợp (tính năng chạm cả backend lẫn extension, đổi hợp đồng API, lên kế hoạch phase mới, review trước khi merge). Định tuyến đúng vai, chạy song song khi an toàn, và bắt buộc có bằng chứng test trước khi báo xong.
---

# Team ielts-translator

Skill này chạy ở **phiên chính** (phiên có quyền gọi Agent và SendMessage). Nó không phải một agent — nó là quy trình bạn tự thực hiện để điều phối 5 agent bên dưới.

## Thành viên

| Agent | Vai | Sở hữu | Không làm |
|---|---|---|---|
| `pm` | Product/Project Manager | Phạm vi, thứ tự ưu tiên, plan trong `docs/superpowers/plans/`, trạng thái theo ledger | Không sửa code, không quyết định kỹ thuật |
| `senior-ba` | Senior Business Analyst | SRS/BRD, đặc tả testable, xuất lên **Confluence** | Không sửa code |
| `techlead` | Tech Lead | Quyết định kỹ thuật, **hợp đồng API giữa hai phía**, review, chốt duyệt | Không mở rộng phạm vi, không viết lại việc người khác |
| `senior-backend` | Senior Backend | Toàn bộ `backend/`, `docker-compose.yml`, `.env.example` | Không sửa `extension/` |
| `senior-frontend` | Senior Frontend | Toàn bộ `extension/` | Không sửa `backend/` |

`senior-ba` là agent global (`~/.claude/agents/`), 4 vai còn lại là agent của project (`.claude/agents/`).

## Bước 0 — Quyết định có cần team không

**Đừng gọi cả team cho việc nhỏ.** Chi phí mỗi agent là một phiên khởi động lạnh, phải đọc lại code từ đầu.

- Sửa một file, một phía, đã rõ phải làm gì → **tự làm, hoặc gọi đúng một agent**. Không dùng skill này.
- Bug chưa rõ nguyên nhân, nằm gọn một phía → gọi một mình `senior-backend` hoặc `senior-frontend`.
- Việc chạm **cả hai phía**, hoặc đổi **hợp đồng API**, hoặc cần **plan nhiều task**, hoặc cần **review trước khi merge** → dùng skill này.

Nói rõ với người dùng bạn chọn hướng nào và vì sao, trước khi dispatch.

## Bước 1 — Định tuyến

Đọc yêu cầu rồi chọn **tập vai tối thiểu** giải quyết được. Không phải việc nào cũng cần đủ 5.

| Loại việc | Chuỗi vai |
|---|---|
| Yêu cầu mơ hồ, chưa rõ làm gì | `pm` chốt phạm vi → dừng, hỏi lại người dùng |
| Cần tài liệu đặc tả (SRS/BRD) | `senior-ba` (hỏi trang Confluence đích trước) |
| Tính năng mới chạm cả hai phía | `pm` → `techlead` (chốt hợp đồng) → `senior-backend` ∥ `senior-frontend` → `techlead` (review) |
| Tính năng một phía, hợp đồng không đổi | agent phía đó → `techlead` (review) |
| Đổi field/status code/mã lỗi của API | `techlead` chốt trước → hai phía sửa đồng thời → `techlead` review |
| Bug một phía | agent phía đó → `techlead` review nếu fix chạm hợp đồng hoặc cấu hình |
| Lập kế hoạch phase mới | `pm` (viết plan) → `techlead` (soi tính khả thi kỹ thuật) |
| Review trước khi merge | `techlead` |

## Bước 2 — Quy tắc dispatch

**Một file chỉ có một agent được sửa tại một thời điểm.** Đây là quy tắc cứng. Hai agent cùng sửa một file sẽ ghi đè nhau âm thầm. Ranh giới `backend/` ↔ `extension/` đã tách sạch nên hai vai implement **được phép chạy song song** — mọi trường hợp khác phải chạy tuần tự.

**Chốt hợp đồng trước khi implement song song.** Nếu thay đổi chạm `extension/src/shared/types.ts` hoặc DTO backend, để `techlead` viết ra hình dạng cuối cùng (tên field, kiểu, status code, mã lỗi) **trước**, rồi đưa nguyên văn hợp đồng đó vào brief của cả hai bên. Song song mà chưa chốt hợp đồng = hai bản không khớp.

**Brief cho mỗi agent phải tự đứng được.** Agent khởi động lạnh, không thấy hội thoại này. Mỗi brief gồm:

1. Mục tiêu, phát biểu theo hành vi quan sát được.
2. Hợp đồng/ràng buộc đã chốt, chép nguyên văn (đừng bảo agent "xem ở trên").
3. File được phép sửa, và file **không** được đụng.
4. Lệnh kiểm chứng bắt buộc chạy.
5. Yêu cầu báo cáo: đã sửa gì, bằng chứng test, ảnh hưởng hợp đồng, việc chưa làm.

**Chạy nền là mặc định.** Dispatch nhiều agent độc lập trong **một** lượt trả lời để chúng chạy song song. Cần hỏi tiếp một agent đã chạy thì dùng `SendMessage` tới tên nó — gọi `Agent` mới là mất sạch ngữ cảnh của nó.

Đặt `name` dễ đọc khi dispatch (`be-translate`, `fe-panel`) để còn nhắn tiếp được.

## Bước 3 — Nghiệm thu, không tin lời khai

Agent báo "xong" chưa phải là xong. Với mỗi báo cáo có sửa code, kiểm tra **output lệnh thật** có trong báo cáo:

```bash
cd backend && mvn test                        # cần Docker cho Testcontainers
cd extension && npm test && npm run build     # type check chỉ nằm trong `npm run build`
```

Thiếu bằng chứng → `SendMessage` bảo nó chạy và dán output, đừng tự chạy hộ rồi cho qua.

Sau khi cả hai phía xong, **luôn** cho `techlead` review diff tổng hợp, kể cả khi từng phía đều xanh — lỗi hay nằm đúng ở chỗ nối giữa hai phía mà không phía nào tự thấy.

## Bước 4 — Tổng hợp cho người dùng

Đừng dán lại nguyên văn báo cáo của các agent. Viết một tổng hợp:

- **Đã làm gì:** theo tính năng, không theo agent.
- **Bằng chứng:** kết quả test hai phía.
- **Kết luận review của techlead:** duyệt / duyệt kèm điều kiện / chưa duyệt.
- **Cần người thật làm:** load lại `extension/dist`, thao tác Chrome, kiểm chứng với Gemini thật.
- **Còn lại & rủi ro:** nói thẳng phần nào chưa xong.

## Ranh giới của cả team

Không agent nào được **tự commit/push/tạo PR** trừ khi người dùng yêu cầu. Nhánh hiện tại là `main` — cảnh báo trước khi commit.

Không ai chạy `docker compose down -v`: lệnh đó xoá volume `ielts_pgdata`, tức xoá sạch sổ từ vựng. Cần reset DB thì hỏi người dùng và nhắc export CSV trước.

## Ví dụ — thêm trường `note` cho mục từ vựng

1. `techlead` chốt hợp đồng: `VocabEntryDto.note: string | null`, `PATCH /api/vocab/{id}` trả 200/404, mã lỗi `NOT_FOUND`.
2. Dispatch song song trong một lượt:
   - `senior-backend`: migration `V3__vocab_note.sql`, entity, DTO, endpoint, `VocabServiceIT` + `VocabControllerIT`. Cấm đụng `extension/`.
   - `senior-frontend`: `shared/types.ts`, message `UPDATE_VOCAB_NOTE`, service worker, UI trong `VocabTab.tsx`, test. Cấm đụng `backend/`.
   - Cả hai nhận **cùng một đoạn hợp đồng chép nguyên văn**.
3. Thu báo cáo, kiểm output `mvn test` và `npm test && npm run build`.
4. `techlead` review diff hai phía, soi đúng chỗ nối: field có khớp không, `null` xử lý thế nào, 404 hiển thị ra sao.
5. Tổng hợp và nêu bước người dùng phải tự kiểm trên Chrome.
