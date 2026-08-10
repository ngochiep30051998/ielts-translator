-- Đăng nhập Google và tách dữ liệu theo người dùng.
-- Xem docs/superpowers/specs/2026-08-10-auth-multi-user-design.md

CREATE TABLE app_user (
    id            BIGSERIAL    PRIMARY KEY,
    -- NULL với hàng do chính migration này tạo ra và chưa ai đăng nhập. Lần đăng nhập đầu
    -- khớp theo EMAIL rồi điền cột này; từ đó về sau khớp theo sub, vì email Google đổi
    -- được còn sub thì không.
    google_sub    VARCHAR(64)  UNIQUE,
    email         VARCHAR(320) NOT NULL UNIQUE,
    display_name  VARCHAR(200),
    picture_url   TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE user_session (
    id           BIGSERIAL   PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    -- SHA-256 hex của token, KHÔNG phải token. Lộ bảng này không cho phép mạo danh ai.
    token_hash   CHAR(64)    NOT NULL UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    revoked_at   TIMESTAMPTZ
);
CREATE INDEX idx_session_user ON user_session (user_id);

CREATE TABLE gemini_usage (
    user_id BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    day     DATE   NOT NULL,
    calls   INT    NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

-- Chủ sở hữu gắn ở ĐÚNG MỘT chỗ. srs_card / srs_distractor / quiz_item đã có
-- vocab_entry_id; review_log treo vào srs_card; quiz_attempt treo vào quiz_item. Nhân cột
-- user_id ra sáu bảng chỉ tạo cơ hội cho hai nguồn sự thật lệch nhau — mà lệch kiểu đó là
-- dữ liệu người này lọt sang người kia, không có lỗi nào nổ ra.
--
-- lookup_cache CỐ Ý không có user_id: nó là cache bản dịch của một chuỗi công khai, dùng
-- chung tiết kiệm quota Gemini thật và không chứa gì riêng tư.
ALTER TABLE vocab_entry ADD COLUMN user_id BIGINT REFERENCES app_user(id) ON DELETE CASCADE;

-- Tài khoản gốc, nhận toàn bộ dữ liệu đã có. ON CONFLICT để migration chạy được cả trên
-- DB trống lẫn DB đã có sẵn email đó.
INSERT INTO app_user (email, display_name)
VALUES (lower('${bootstrap_email}'), 'Chủ sở hữu dữ liệu cũ')
ON CONFLICT (email) DO NOTHING;

UPDATE vocab_entry
SET user_id = (SELECT id FROM app_user WHERE email = lower('${bootstrap_email}'))
WHERE user_id IS NULL;

ALTER TABLE vocab_entry ALTER COLUMN user_id SET NOT NULL;

-- Ràng buộc cũ TOÀN CỤC: hai người không được phép cùng lưu từ "mitigate".
ALTER TABLE vocab_entry DROP CONSTRAINT uq_vocab_term_pos;
ALTER TABLE vocab_entry ADD CONSTRAINT uq_vocab_user_term_pos UNIQUE (user_id, term, pos);
CREATE INDEX idx_vocab_user ON vocab_entry (user_id);
