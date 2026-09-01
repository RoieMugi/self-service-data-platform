# Session 009 - Processing Run and Validation Tracking

**Date:** 2026-09-01

**Status:** Complete

## Objective

Persist processing attempts, validation outcomes, output metadata, and failures
in PostgreSQL so users can inspect what happened after processing an upload.

## What we built

- A `processing_runs` PostgreSQL table linked to uploads.
- Run states: `running`, `succeeded`, and `failed`.
- Database constraints protecting valid lifecycle states.
- Separate validation outcomes: `passed`, `failed`, or unknown.
- An index for retrieving runs by upload UUID.
- Versioned SQL migrations for the existing PostgreSQL database.
- Run creation before DuckDB processing begins.
- Successful-run updates containing row count and curated object key.
- Failure updates distinguishing validation and infrastructure failures.
- `GET /processing-runs/{run_id}` for retrieving durable run state.
- Expanded automated coverage from 20 to 27 tests.

## Concepts learned

- PostgreSQL is the durable source of truth for processing state.
- MinIO stores physical data while PostgreSQL stores location and lifecycle
  metadata.
- A migration evolves an existing database; `init.sql` configures a new one.
- `BEGIN` and `COMMIT` make a migration atomic.
- Database constraints protect invariants even if application code is wrong.
- State transitions should update all related fields atomically.
- Validation failures and infrastructure failures have different meanings.
- Pytest monkeypatching replaces real dependencies during isolated tests.
- FastAPI decorators register Python functions as HTTP route handlers.

## Processing lifecycle

```text
POST /uploads/{upload_id}/process
    -> verify upload exists
    -> create PostgreSQL run with status=running
    -> download raw CSV from MinIO
    -> convert and validate with DuckDB
    -> upload curated Parquet to MinIO
    -> update run to succeeded

Expected failure
    -> update run to failed
    -> record validation outcome when known
    -> return a safe HTTP error
```

## Design decisions

- PostgreSQL remains the authoritative run-history store.
- Processing remains synchronous for this checkpoint.
- Each processing request creates a new run.
- RabbitMQ may later distribute asynchronous processing jobs.
- Kafka or Redpanda may later publish durable, replayable platform events.
- A successful run requires at least one data row.
- Infrastructure failures leave validation status unknown.
- Detailed exceptions remain in logs; PostgreSQL stores safe error summaries.
- Applied migrations are followed by corrective migrations rather than silently
  rewritten.

## Files changed

- `app/main.py`
- `db/init.sql`
- `db/migrations/001_add_processing_runs.sql`
- `db/migrations/002_add_processing_run_constraints.sql`
- `test_health.py`
- `README.md`
- `Platform_Engineering_Study_Notes.md`
- `docs/sessions/README.md`
- `docs/sessions/TIMELINE.md`
- `docs/sessions/009-processing-run-tracking.md`

## Verification

- Both migrations applied successfully to the existing PostgreSQL database.
- PostgreSQL inspection confirmed the primary key, upload foreign key, index,
  and three lifecycle constraints.
- `python -m pytest -q` completed with 27 passing tests and one third-party
  Starlette pending-deprecation warning.
- A live valid CSV run succeeded with three rows and a curated Parquet object.
- `GET /processing-runs/{run_id}` returned the persisted successful state.
- Direct PostgreSQL inspection matched the API response.
- A live header-only CSV returned HTTP 422.
- Its run persisted as failed with `validation_status=failed`, no row count,
  no curated object key, and a safe error message.

## Blockers resolved

The initial migration accidentally contained a placeholder instead of table
columns. Its transaction rolled back when index creation failed.

The corrected table migration succeeded, and a second migration added the
constraints absent from the already-created table. This demonstrated why
migrations are transactional and why applied migrations should be preserved.

An empty-row validation check was initially mis-indented, causing every
successful conversion to return HTTP 422. A focused success test exposed the
control-flow error, and correcting the indentation restored the expected path.

## Next checkpoint

Add continuous integration with GitHub Actions so tests and configuration checks
run automatically for repository changes.
