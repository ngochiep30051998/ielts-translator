-- Mồi nhử cho câu trắc nghiệm ôn tập, do Gemini sinh một lần rồi cache.
-- prompt_version theo đúng nguyên tắc của lookup_cache: sửa prompt phải tăng version
-- trong file, bản ghi version cũ coi như không có và sẽ được sinh lại.
CREATE TABLE srs_distractor (
    id             BIGSERIAL   PRIMARY KEY,
    vocab_entry_id BIGINT      NOT NULL UNIQUE
                   REFERENCES vocab_entry(id) ON DELETE CASCADE,
    vi_options     JSONB       NOT NULL,
    en_options     JSONB       NOT NULL,
    prompt_version INT         NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
