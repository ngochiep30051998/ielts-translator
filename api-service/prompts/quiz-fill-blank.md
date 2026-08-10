version: 1
---
Bạn đang ra đề luyện từ vựng IELTS dạng điền vào chỗ trống.

Danh sách từ (mỗi dòng: từ | từ loại | nghĩa tiếng Việt):
{{TERMS}}

Với MỖI từ trong danh sách, sinh đúng một câu tiếng Anh học thuật mức IELTS band 6.5–7.

Trả về JSON đúng schema đã cho, mảng `items`, mỗi phần tử gồm:

- term: đúng từ trong danh sách, chép nguyên văn.
- sentence: câu tiếng Anh trong đó DẠNG ĐÚNG của từ bị thay bằng đúng ba gạch dưới `___`.
- answer: dạng từ đã bị che, chép đúng như nó sẽ xuất hiện trong câu (kể cả đuôi -ed, -ing, -s).
- hint: gợi ý ngắn bằng tiếng Việt, tối đa 10 từ, KHÔNG chứa đáp án.

Quy tắc bắt buộc:
- Câu phải có đủ ngữ cảnh để chỉ MỘT từ điền vào là hợp lý. Câu chung chung kiểu
  "This is very ___." là đề tồi.
- `___` xuất hiện đúng MỘT lần trong câu.
- Đáp án KHÔNG được xuất hiện lần nữa ở bất kỳ đâu khác trong chính câu đó, dù viết
  hoa hay viết thường, dù ở dạng nào.
- `hint` KHÔNG được chứa đáp án dưới bất kỳ dạng nào — gợi ý mà lộ đáp án thì câu hỏi
  mất sạch giá trị.
- Câu dài 10–25 từ, giọng học thuật, chủ đề IELTS thường gặp (môi trường, giáo dục,
  công nghệ, y tế, đô thị hoá).
- Số phần tử trong `items` bằng đúng số từ trong danh sách, đúng thứ tự.
