BEGIN;

CREATE TABLE IF NOT EXISTS processing_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id UUID NOT NULL REFERENCES uploads(id),
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    row_count BIGINT,
    curated_object_key TEXT,
    validation_status TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_processing_runs_upload_id
    ON processing_runs(upload_id);

COMMIT;
