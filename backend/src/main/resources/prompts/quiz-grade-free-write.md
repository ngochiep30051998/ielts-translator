version: 1
---
Bạn đang chấm một câu do người học IELTS viết để luyện dùng một từ cụ thể.

Từ phải dùng: {{TERM}}
Từ loại: {{POS}}
Nghĩa tiếng Việt: {{MEANING_VI}}
Định nghĩa tiếng Anh: {{DEFINITION_EN}}

Câu người học viết:
{{ANSWER}}

Trả về JSON đúng schema đã cho:

- meaning_ok: true khi người học dùng từ ĐÚNG NGHĨA và đúng ngữ cảnh. Dùng đúng chính tả
  nhưng sai nghĩa thì là false.
- grammar_ok: true khi câu đúng ngữ pháp và tự nhiên. Lỗi nhỏ không ảnh hưởng nghĩa
  (thiếu mạo từ, sai giới từ nhẹ) vẫn tính true, kèm nhắc trong feedback.
- band_ok: true khi câu đạt mức từ vựng và cấu trúc của IELTS band 6.5 trở lên.
- score: 0–100. Sai nghĩa thì dưới 40 bất kể ngữ pháp. Đúng nghĩa, đúng ngữ pháp, chưa
  đạt band 6.5 thì 60–75. Đạt cả ba thì 85–100.
- feedback_vi: nhận xét bằng TIẾNG VIỆT ĐỦ DẤU, 2–3 câu, chỉ thẳng chỗ sai và vì sao sai.
  Không khen chung chung.
- improved_version: câu tiếng Anh đã sửa, giữ nguyên ý người học, nâng lên mức band 6.5–7,
  và vẫn dùng từ {{TERM}}.

Nếu người học KHÔNG dùng từ {{TERM}} trong câu, đặt meaning_ok = false, score = 0, và nói
rõ điều đó trong feedback_vi.
