-- Đề quiz sinh sẵn và lịch sử làm bài.
--
-- KHÔNG phải V4: V4__srs_distractor.sql đã tồn tại và đã chạy. Spec Phase 3 viết
-- "V4__quiz.sql" là viết trước khi màn ôn tập trắc nghiệm ra đời.
--
-- prompt_version theo đúng nguyên tắc của lookup_cache và srs_distractor: sửa nội dung
-- prompt phải tăng version trong file, và bản ghi version cũ coi như không có.
CREATE TABLE quiz_item (
    id             BIGSERIAL   PRIMARY KEY,
    vocab_entry_id BIGINT      NOT NULL
                   REFERENCES vocab_entry(id) ON DELETE CASCADE,
    type           VARCHAR(24) NOT NULL,
    payload        JSONB       NOT NULL,
    prompt_version INT         NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Không UNIQUE trên (vocab_entry_id, type): một từ được phép có nhiều đề cùng loại theo
-- thời gian, và item đã làm rồi KHÔNG bị xoá — quiz_attempt là dữ liệu lịch sử, và số
-- lượt làm chính là tiêu chí ưu tiên ứng viên.
CREATE INDEX idx_quiz_item_vocab ON quiz_item (vocab_entry_id, type);

-- correct là bổ sung so với design gốc: score một mình không phân biệt được "sai"
-- (score = 0) với "chưa chấm".
--
-- improved_version tách riêng khỏi ai_feedback vì hợp đồng API trả hai trường khác
-- nhau (feedback: nhận xét tiếng Việt; improvedVersion: câu đã sửa). Nhét chung một
-- cột rồi tách bằng chuỗi phân cách là thứ sẽ hỏng ở lần đầu Gemini trả dấu phân cách.
-- NULL với FILL_BLANK và COLLOCATION_CHOICE — hai loại đó không có khái niệm câu viết lại.
CREATE TABLE quiz_attempt (
    id               BIGSERIAL   PRIMARY KEY,
    quiz_item_id     BIGINT      NOT NULL REFERENCES quiz_item(id) ON DELETE CASCADE,
    user_answer      TEXT        NOT NULL,
    correct          BOOLEAN     NOT NULL,
    score            INT         NOT NULL,
    ai_feedback      TEXT,
    improved_version TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_quiz_attempt_item ON quiz_attempt (quiz_item_id);
