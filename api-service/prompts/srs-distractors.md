version: 1
---
Bạn đang tạo mồi nhử cho một câu trắc nghiệm từ vựng IELTS.

Từ: {{TERM}}
Từ loại: {{POS}}
Nghĩa tiếng Việt đúng: {{MEANING_VI}}
Định nghĩa tiếng Anh: {{DEFINITION_EN}}

Trả về JSON đúng schema đã cho, gồm hai mảng:

- vi_options: đúng 3 nghĩa tiếng Việt SAI, dùng làm đáp án nhiễu khi hỏi "{{TERM}} nghĩa là gì".
- en_options: đúng 3 từ tiếng Anh SAI, dùng làm đáp án nhiễu khi hỏi "từ nào có nghĩa {{MEANING_VI}}".

Quy tắc bắt buộc:
- Mồi nhử phải SAI rõ ràng nhưng KHÓ loại trừ: cùng từ loại, cùng miền nghĩa hoặc cùng
  ngữ cảnh học thuật với đáp án đúng. Ba nghĩa hoàn toàn không liên quan là mồi nhử tồi.
- KHÔNG được đồng nghĩa, gần nghĩa, hay là cách diễn đạt khác của đáp án đúng. Người học
  phải chỉ có đúng MỘT lựa chọn đúng.
- KHÔNG lặp lại chính {{TERM}} hay chính {{MEANING_VI}} dưới bất kỳ dạng nào.
- en_options phải là từ tiếng Anh có thật, cùng từ loại với {{TERM}}, độ khó tương đương.
- vi_options viết ngắn như một mục từ điển, tối đa 8 từ, không viết thành câu.
- Ba phần tử trong cùng một mảng phải khác nhau.
