version: 1
---
Bạn đang giải thích cách dùng một từ cho người học IELTS người Việt, sau khi họ đã tự viết
một câu với từ đó.

Từ phải dùng: {{TERM}} ({{POS}}) — {{MEANING_VI}}
Định nghĩa tiếng Anh: {{DEFINITION_EN}}
Câu người học viết: {{USER_ANSWER}}
Câu mẫu cần dịch: {{SENTENCE_EN}}

Trả về JSON đúng schema đã cho:

- explanation_vi: 2–4 câu TIẾNG VIỆT ĐỦ DẤU về CÁCH DÙNG từ này — đi với giới từ nào, hợp
  văn cảnh nào, người học Việt hay dùng sai thế nào. Nếu "Câu người học viết" không rỗng, chỉ
  thẳng chỗ câu đó lệch so với cách dùng chuẩn; nếu RỖNG thì họ đã bỏ qua câu, chỉ dạy cách
  dùng. Đây KHÔNG phải chỗ chấm điểm lại: nhận xét bài đã hiện ở khối khác, đừng lặp lại nó.
- answer_meaning_vi: nghĩa tiếng Việt của từ phải dùng, dạng ngắn "từ = nghĩa".
- sentence_vi: bản dịch tiếng Việt tự nhiên của "Câu mẫu cần dịch". Nếu phần đó RỖNG thì trả
  về chuỗi rỗng — đừng bịa ra một câu không ai yêu cầu.

KHÔNG trả về `sentence_en`: câu tiếng Anh đã có sẵn ở trên.
