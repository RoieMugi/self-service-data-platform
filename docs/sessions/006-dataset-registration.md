# Session 006 - Dataset Registration

**Date:** 2026-08-25

**Status:** Complete
## Objective

Register logical datasets through FastAPI and persist their metadata in
PostgreSQL.

## What we built

- A PostgreSQL `datasets` table.
- Docker Compose mounting for the database initialization script.
- Request and response models for dataset registration.
- `POST /datasets` returning HTTP 201 for successful registration.
- Database-generated UUIDs and creation timestamps.
- HTTP 409 responses for duplicate dataset names.
- HTTP 422 validation for empty and whitespace-only names.
- Automated tests for success, duplication, and invalid input.

## Concepts learned

- PostgreSQL stores platform metadata while MinIO will store data files.
- A logical dataset has a stable identity independent of individual filenames.
- Database initialization and database migration are different processes.
- Database constraints protect data integrity.
- Parameterized SQL prevents SQL injection.
- FastAPI and Pydantic define and validate the HTTP contract.
- Mocking isolates API behavior from external database dependencies.
- Manual integration tests and automated unit tests provide different evidence.

## Files changed

- `app/main.py`
- `docker-compose.yml`
- `db/init.sql`
- `test_health.py`

## Verification

- Validated the Compose configuration with `docker compose config`.
- Started the API and PostgreSQL successfully.
- Confirmed PostgreSQL reported healthy.
- Applied `db/init.sql` to the existing database.
- Inspected the resulting `datasets` table.
- Inserted a dataset directly through PostgreSQL.
- Verified PostgreSQL rejected a duplicate dataset name.
- Registered the `sales` dataset through `POST /datasets`.
- Verified duplicate registration returned HTTP 409.
- Verified invalid input returned HTTP 422.
- `python -m pytest -q` completed with 6 passing tests.

## Design decision

Dataset registration stores only stable logical metadata:

- `id`
- `name`
- `description`
- `created_at`

Physical filenames will belong to future upload records because one dataset may
receive many files over time.

## Next checkpoint

Add MinIO and begin storing uploaded CSV files in object storage while recording
their metadata in PostgreSQL.
