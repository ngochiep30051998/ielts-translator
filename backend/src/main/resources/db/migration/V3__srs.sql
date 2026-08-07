CREATE TABLE srs_card (
    id              BIGSERIAL   PRIMARY KEY,
    vocab_entry_id  BIGINT      NOT NULL UNIQUE
                    REFERENCES vocab_entry(id) ON DELETE CASCADE,
    ease_factor     DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    interval_days   INT         NOT NULL DEFAULT 0,
    repetitions     INT         NOT NULL DEFAULT 0,
    lapses          INT         NOT NULL DEFAULT 0,
    due_date        DATE        NOT NULL,
    state           VARCHAR(16) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_srs_due ON srs_card (due_date, state);

CREATE TABLE review_log (
    id            BIGSERIAL   PRIMARY KEY,
    card_id       BIGINT      NOT NULL REFERENCES srs_card(id) ON DELETE CASCADE,
    rating        VARCHAR(8)  NOT NULL,
    reviewed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_interval INT         NOT NULL,
    new_interval  INT         NOT NULL
);

CREATE INDEX idx_review_log_reviewed_at ON review_log (reviewed_at);

-- Backfill: mọi từ đơn đã lưu ở Phase 1 vào lịch ôn ngay.
-- pos = 'phrase' là câu, không làm flashcard được nên bỏ qua.
INSERT INTO srs_card (vocab_entry_id, due_date, state)
SELECT id, CURRENT_DATE, 'NEW' FROM vocab_entry WHERE pos <> 'phrase';
