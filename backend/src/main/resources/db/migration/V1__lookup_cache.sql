CREATE TABLE lookup_cache (
    id             BIGSERIAL    PRIMARY KEY,
    source_hash    VARCHAR(64)  NOT NULL UNIQUE,
    source_text    TEXT         NOT NULL,
    direction      VARCHAR(16)  NOT NULL,
    mode           VARCHAR(16)  NOT NULL,
    model          VARCHAR(64)  NOT NULL,
    prompt_version INTEGER      NOT NULL,
    response       JSONB        NOT NULL,
    hit_count      INTEGER      NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_lookup_cache_created_at ON lookup_cache (created_at DESC);
