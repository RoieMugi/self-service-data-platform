# Session 014 - Queued Runs and Processing Separation

**Date:** 2026-09-08

**Status:** Complete for preparation and refactoring; asynchronous execution remains pending.

## Objective

Prepare the database lifecycle and processing code for a future queue and worker,
while preserving the existing synchronous API behavior.

## Work completed, step by step

1. Reviewed project documentation, Session 013, and repository memory skills.
2. Explained API, broker, and worker responsibilities. Local containers share
   the host computer's CPU and RAM; client machines only perform their own work.
3. Distinguished job acceptance from completion and submission time from start
   time. Identified reliable database-to-queue handoff as future design work.
4. Added `queued` and `created_at` to the fresh-database schema. Removed the
   automatic start timestamp and allowed it to remain NULL while queued.
5. Updated state constraints, including explicit non-NULL row count and
   validation status for successful runs. Failed runs may have no start time.
6. Changed current run creation to explicitly set `started_at`, preserving
   synchronous processing compatibility with both schema versions.
7. Wrote transactional migration 003 and explored existing PostgreSQL records
   and MinIO raw/curated storage. Applied the migration once to the local database;
   nine historical runs received `created_at` from their existing start time.
8. Verified the schema, accepted a valid queued row, and rejected a queued row
   with a start timestamp. Rolled back both test transactions.
9. Reprocessed a known three-row upload successfully after the migration.
10. Extracted `execute_processing(upload_id, correlation_id)` from the HTTP
    endpoint. Added `ProcessingError` and translated its categories into
    HTTP 404, 422, 503, and 500 in the endpoint wrapper.
11. Rebuilt the API and verified successful live processing after the refactor.
12. Recorded the session and polished spacing around the changed Python class,
    decorator, and function, plus argument indentation in the curated-storage
    exception. Corrected the README architecture to describe
    synchronous processing rather than an already deployed worker.

## Concepts and decisions

- PostgreSQL stores metadata and run history; MinIO stores CSV and Parquet bytes.
- SQL files take effect only when executed. Initialization is for an empty
  database; migrations update an existing persistent database.
- Migration 003 uses BEGIN/COMMIT and was executed with ON_ERROR_STOP=1.
  It is not rerunnable after success and is unnecessary on a fresh updated schema.
- SQL CHECK accepts NULL as well as TRUE, so required success fields need
  explicit non-NULL conditions.
- A correlation ID is passed as an ordinary value to processing code.
- Processing errors describe failures; the HTTP wrapper chooses response codes.
- Processing remains synchronous and continues to create a new running record.
  There is no RabbitMQ service, worker container, or HTTP 202 contract yet.

## Files changed

- `app/main.py`
- `db/init.sql`
- `db/migrations/003_add_queued_processing_runs.sql`
- `README.md`
- `docs/sessions/README.md`
- `docs/sessions/TIMELINE.md`
- `docs/sessions/014-queued-run-preparation.md`

## Verification

The user executed the tests, Docker commands, SQL checks, and HTTP requests and
shared their results in the session.

- Initial `python -m pytest -q`: `43 passed, 1 warning in 4.73s`.
  The warning was the existing Starlette multipart pending deprecation.
- After refactoring, `python -m pytest -q`: user reported `43 passed`.
- `docker compose up -d --build api` succeeded before migration and again after
  refactoring; PostgreSQL and MinIO were healthy and the API started.
- Migration output ended with COMMIT and included `UPDATE 9`.
- `\d processing_runs` confirmed columns, defaults, and constraints.
- Valid queued INSERT returned an automatic creation time and NULL start time.
- Invalid queued INSERT with a start time failed `processing_runs_state_check`.
- Both temporary inserts were rolled back.
- Upload `d64523df-8a01-4f21-a9a0-51fc872d45fb` processed successfully twice:
  run `e8386c5f-01fd-4581-af20-2579524771b1` after migration and
  run `3aca8335-f3db-407f-b0e5-45d14a3e8817` after refactoring.
  Both returned `succeeded`, 3 rows, Parquet output, and validation `passed`.
- These runs write the same upload-based curated object location; the run
  history is distinct, but output versioning has not been introduced.
- Session-end cleanup changes whitespace only in Python; no new test run was
  performed for that cleanup. Git commit/push and new CI results are pending
  user execution and are not claimed as complete.

## Blockers and follow-up observations

- No blocker for this increment.
- Compose reports the old cAdvisor container as an orphan; it was not removed.
- Dashboard review found a trailing space in the memory query's data source UID
  and a duration description saying recent while its query uses cumulative
  buckets. These observations were not fixed or live-tested in this session.

## Next small step

Separate run creation from execution so processing can accept an existing run.
Then design safe queued-to-running claiming, reliable submission handoff,
duplicate delivery/recovery behavior, and queue/worker integration. Preserve
correlation across messages and plan worker metrics collection before moving
execution out of the API process. RabbitMQ remains the proposed broker candidate.
