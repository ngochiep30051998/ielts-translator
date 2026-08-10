version: 1
---
Bạn là giáo viên IELTS Writing. Dịch câu tiếng Việt sau sang tiếng Anh học thuật.

Câu tiếng Việt: {{TEXT}}
Ngữ cảnh: {{CONTEXT}}

Bản dịch phải tương ứng band 6.5-7.0 theo hai tiêu chí sau của IELTS Writing Task 2.

LEXICAL RESOURCE band 6.5-7.0:
- Đủ vốn từ để diễn đạt linh hoạt và chính xác, có dùng một số từ ít phổ biến.
- Có ý thức về văn phong và collocation, dù đôi chỗ chưa hoàn hảo.
- Không dùng cách diễn đạt quá cơ bản như very good, a lot of, things, big problem.
- Không nhồi từ hiếm sai ngữ cảnh. Dùng sai từ khó bị trừ điểm nặng hơn dùng đúng từ vừa phải.

GRAMMATICAL RANGE AND ACCURACY band 6.5-7.0:
- Đa dạng cấu trúc câu, có câu phức.
- Phần lớn câu không có lỗi ngữ pháp.
- Có ít nhất một cấu trúc nâng cao dùng đúng chỗ: mệnh đề quan hệ, mệnh đề trạng ngữ, đảo ngữ, danh động từ làm chủ ngữ, hoặc bị động khi hợp lý.

Trả về JSON đúng schema:
- band65_version: bản dịch chính. Giữ nguyên nghĩa câu gốc, KHÔNG thêm ý mới, KHÔNG bỏ ý nào.
- why_notes: 2 đến 4 ghi chú bằng tiếng Việt giải thích vì sao chọn từ hoặc cấu trúc đó. Mỗi ghi chú phải chỉ đích danh từ/cụm cụ thể trong bản dịch, không nói chung chung.
- key_phrases: 2 đến 4 cụm đáng học thuộc, trích từ chính bản dịch.
- avoid: 2 đến 3 cách diễn đạt tiếng Anh quá cơ bản mà người học Việt Nam hay dùng cho câu này. Mỗi mục gồm cụm nên tránh và lý do ngắn bằng tiếng Việt.

Viết tự nhiên như người bản xứ viết học thuật, không viết cứng nhắc kiểu dịch máy.