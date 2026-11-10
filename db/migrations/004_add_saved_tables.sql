BEGIN;

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
    -- Exactly one parent preserves provenance from a run or another saved table.
    CHECK ((source_run_id IS NOT NULL) <> (source_table_id IS NOT NULL))
);

COMMIT;
