version: 1
---
Bạn đang giải thích đáp án một câu điền từ cho người học IELTS người Việt.

Câu hỏi (dấu `___` là chỗ trống): {{SENTENCE}}
Đáp án đúng: {{ANSWER}}
Từ gốc trong sổ từ: {{TERM}} ({{POS}}) — {{MEANING_VI}}
Người học đã điền: {{USER_ANSWER}}

Trả về JSON đúng schema đã cho:

- explanation_vi: 2–4 câu TIẾNG VIỆT ĐỦ DẤU. Nói vì sao đáp án đúng hợp với chính câu này —
  dựa vào chủ ngữ, tân ngữ, collocation, dạng từ, chứ không nêu định nghĩa từ điển suông.
  Nếu "Người học đã điền" KHÁC đáp án và không rỗng, chỉ thẳng vì sao từ đó không hợp ở đây.
  Nếu phần đó RỖNG thì người học đã bỏ qua câu — đừng nhắc tới lựa chọn của họ dưới bất kỳ
  hình thức nào, chỉ giải thích đáp án.
- answer_meaning_vi: nghĩa tiếng Việt của ĐÁP ÁN trong đúng ngữ cảnh câu này, dạng ngắn
  "từ = nghĩa". Nghĩa trong sổ từ ở trên là tham khảo — đừng mâu thuẫn với nó.
- sentence_vi: bản dịch tiếng Việt tự nhiên của câu đã điền đáp án vào chỗ trống.

KHÔNG trả về `sentence_en`: câu tiếng Anh đã có sẵn, chép lại chỉ tạo cơ hội chép sai.
