CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    original_filename TEXT NOT NULL,
    object_key TEXT NOT NULL UNIQUE,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processing_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id UUID NOT NULL REFERENCES uploads(id),
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    row_count BIGINT,
    curated_object_key TEXT,
    validation_status TEXT,
    error_message TEXT,

    CONSTRAINT processing_runs_status_check
        CHECK (status IN ('running', 'succeeded', 'queued', 'failed')),

    CONSTRAINT processing_runs_validation_status_check
        CHECK (
            validation_status IS NULL
            OR validation_status IN ('passed', 'failed')
        ),

    CONSTRAINT processing_runs_state_check
        CHECK (
            (
                status = 'running'
                AND started_at IS NOT NULL
                AND completed_at IS NULL
                AND row_count IS NULL
                AND curated_object_key IS NULL
                AND validation_status IS NULL
                AND error_message IS NULL
            )
            OR
            (
                status = 'queued'
                AND started_at IS NULL
                AND completed_at IS NULL
                AND row_count IS NULL
                AND curated_object_key IS NULL
                AND validation_status IS NULL
                AND error_message IS NULL
            )
            OR
            (
                status = 'succeeded'
                AND started_at IS NOT NULL
                AND completed_at IS NOT NULL
                AND row_count IS NOT NULL
                AND row_count > 0
                AND curated_object_key IS NOT NULL
                AND validation_status IS NOT NULL
                AND validation_status = 'passed'
                AND error_message IS NULL
            )
            OR
            (
                status = 'failed'
                AND completed_at IS NOT NULL
                AND row_count IS NULL
                AND curated_object_key IS NULL
                AND error_message IS NOT NULL
                AND (
                    validation_status IS NULL
                    OR validation_status = 'failed'
                )
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_processing_runs_upload_id
    ON processing_runs(upload_id);