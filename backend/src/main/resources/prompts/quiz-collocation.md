version: 1
---
Bạn đang ra đề luyện collocation cho người học IELTS.

Danh sách từ (mỗi dòng: từ | từ loại | nghĩa tiếng Việt):
{{TERMS}}

Với MỖI từ trong danh sách, sinh đúng một câu hỏi trắc nghiệm về collocation.

Trả về JSON đúng schema đã cho, mảng `items`, mỗi phần tử gồm:

- term: đúng từ trong danh sách, chép nguyên văn.
- question: câu hỏi bằng TIẾNG VIỆT ĐỦ DẤU, dạng
  "Cụm nào đi với «{từ}» là tự nhiên trong tiếng Anh học thuật?"
- options: đúng 4 cụm tiếng Anh, mỗi cụm 2–4 từ và đều có chứa từ đang hỏi.
- correct_index: vị trí (0–3) của cụm ĐÚNG trong `options`.

Quy tắc bắt buộc:
- `question` phải là tiếng Việt. Cả ba loại quiz đều hiển thị đề bài bằng tiếng Việt;
  trả về tiếng Anh là làm lệch một mình loại này.
- Đúng MỘT cụm là collocation tự nhiên, người bản ngữ thật sự dùng.
- Ba cụm còn lại phải SAI theo kiểu người học Việt Nam hay mắc: đúng ngữ pháp nhưng
  không ai nói như vậy. Ba cụm sai một cách lố bịch là mồi nhử tồi.
- Bốn cụm phải khác nhau, không cụm nào là biến thể chỉ khác hoa thường của cụm khác.
- Số phần tử trong `items` bằng đúng số từ trong danh sách, đúng thứ tự.
