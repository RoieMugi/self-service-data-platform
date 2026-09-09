BEGIN;

ALTER TABLE processing_runs
    ADD COLUMN created_at TIMESTAMPTZ;

UPDATE processing_runs
SET created_at = started_at;

ALTER TABLE processing_runs
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE processing_runs
    ALTER COLUMN started_at DROP NOT NULL,
    ALTER COLUMN started_at DROP DEFAULT;

ALTER TABLE processing_runs
    DROP CONSTRAINT processing_runs_status_check;

ALTER TABLE processing_runs
    ADD CONSTRAINT processing_runs_status_check
    CHECK (status IN ('queued', 'running', 'succeeded', 'failed'));

ALTER TABLE processing_runs
    DROP CONSTRAINT processing_runs_state_check;

ALTER TABLE processing_runs
    ADD CONSTRAINT processing_runs_state_check
    CHECK (
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
    );

COMMIT;