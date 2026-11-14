BEGIN;

ALTER TABLE processing_runs
    ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS claim_token UUID,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_processing_runs_expired_lease
    ON processing_runs (lease_expires_at)
    WHERE status = 'running';

CREATE TABLE IF NOT EXISTS processing_outbox (
    run_id UUID PRIMARY KEY REFERENCES processing_runs(id),
    correlation_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_processing_outbox_pending
    ON processing_outbox (created_at, run_id)
    WHERE published_at IS NULL;

ALTER TABLE saved_tables ADD COLUMN IF NOT EXISTS operation_id UUID;
CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_tables_operation_id
    ON saved_tables (operation_id) WHERE operation_id IS NOT NULL;

COMMIT;
