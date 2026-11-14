BEGIN;

ALTER TABLE processing_runs
    ADD CONSTRAINT processing_runs_status_check
    CHECK (status IN ('running', 'succeeded', 'failed'));

ALTER TABLE processing_runs
    ADD CONSTRAINT processing_runs_validation_status_check
    CHECK (
        validation_status IS NULL
        OR validation_status IN ('passed', 'failed')
    );

ALTER TABLE processing_runs
    ADD CONSTRAINT processing_runs_state_check
    CHECK (
        (
            status = 'running'
            AND completed_at IS NULL
            AND row_count IS NULL
            AND curated_object_key IS NULL
            AND validation_status IS NULL
            AND error_message IS NULL
        )
        OR
        (
            status = 'succeeded'
            AND completed_at IS NOT NULL
            AND row_count > 0
            AND curated_object_key IS NOT NULL
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