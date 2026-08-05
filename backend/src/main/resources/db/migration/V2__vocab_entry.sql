CREATE TABLE vocab_entry (
    id              BIGSERIAL   PRIMARY KEY,
    term            TEXT        NOT NULL,
    lemma           TEXT,
    lang            VARCHAR(8)  NOT NULL,
    pos             VARCHAR(16) NOT NULL DEFAULT '',
    ipa             TEXT,
    meaning_vi      TEXT        NOT NULL,
    definition_en   TEXT,
    cefr            VARCHAR(4),
    band_level      VARCHAR(8),
    tags            TEXT[]      NOT NULL DEFAULT '{}',
    source_url      TEXT,
    source_sentence TEXT,
    collocations    JSONB       NOT NULL DEFAULT '[]'::jsonb,
    examples        JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_vocab_term_pos UNIQUE (term, pos)
);

CREATE INDEX idx_vocab_created_at ON vocab_entry (created_at DESC);
CREATE INDEX idx_vocab_tags ON vocab_entry USING GIN (tags);
