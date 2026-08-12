-- Phân biệt lượt ôn theo lịch với lượt luyện thêm.
--
-- `DEFAULT 'SCHEDULED'` là phần quan trọng nhất của migration này: mọi dòng đang có đều
-- đúng là lượt ôn theo lịch, nên default backfill chính xác toàn bộ lịch sử mà không cần
-- câu UPDATE nào, và không con số nào ở tab Thống kê đổi.
--
-- Migration KHÔNG chạy lúc cold start trên Vercel (nhiều instance cùng ALTER TABLE là công
-- thức khoá lẫn nhau) — trên Supabase phải chạy tay một lần.
ALTER TABLE review_log ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'SCHEDULED';
