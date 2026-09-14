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

CREATE TABLE IF NOT EXISTS saved_tables (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (length(btrim(name)) BETWEEN 1 AND 100),
    description TEXT CHECK (length(description) <= 500),
    source_run_id UUID REFERENCES processing_runs(id),
    source_table_id UUID REFERENCES saved_tables(id),
    query_sql TEXT NOT NULL CHECK (length(btrim(query_sql)) BETWEEN 1 AND 10000),
    object_key TEXT NOT NULL UNIQUE,
    row_count BIGINT NOT NULL CHECK (row_count BETWEEN 0 AND 100000),
    size_bytes BIGINT NOT NULL CHECK (size_bytes BETWEEN 1 AND 20971520),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((source_run_id IS NOT NULL) <> (source_table_id IS NOT NULL))
);
