# Session 007 - MinIO Raw Object Storage

**Date:** 2026-08-26

**Status:** Complete

## Objective

Store CSV uploads for registered datasets in MinIO and record their object
metadata in PostgreSQL.

## What we built

- A persistent MinIO service managed through Docker Compose.
- A private `raw` bucket created by an idempotent initialization container.
- An `uploads` PostgreSQL table linked to registered datasets.
- `POST /datasets/{dataset_id}/uploads`.
- CSV extension, empty-file, and 10 MiB size validation.
- Unique object keys based on dataset and upload UUIDs.
- Compensating object deletion when metadata persistence fails.
- Automated tests for upload success and failure paths.

## Concepts learned

- PostgreSQL acts as the metadata control plane.
- MinIO acts as the object-storage data plane.
- A logical dataset can own multiple physical file uploads.
- Docker named volumes preserve objects across container replacement.
- Compose service names provide internal DNS.
- Initialization containers make infrastructure setup reproducible.
- Cross-system operations require compensating actions.
- Unit tests and live integration verification provide different evidence.

## Files changed

- `app/main.py`
- `docker-compose.yml`
- `db/init.sql`
- `requirements.txt`
- `test_health.py`
- `docs/sessions/007-minio-raw-storage.md`

## Verification

- `docker compose config` validated the Compose configuration.
- MinIO became healthy on ports 9000 and 9001.
- The `raw` bucket was created and remained private.
- The initialization container completed with exit code 0.
- The `uploads` table and its constraints were inspected in PostgreSQL.
- `python -m pytest -q` completed with 12 passing tests.
- A live CSV was uploaded through FastAPI.
- The object was verified in MinIO.
- Its metadata row was verified in PostgreSQL.
- The object remained available after restarting MinIO.

## Design decisions

- Objects use the key format
  `{dataset_id}/{upload_id}/{sanitized_filename}` inside the `raw` bucket.
- PostgreSQL stores object metadata, while MinIO stores file bytes.
- Duplicate filenames are allowed because upload UUIDs prevent collisions.
- Uploads are limited to 10 MiB for the initial local implementation.
- CSV content validation and transformation are deferred to processing runs.

## Next checkpoint

Execute CSV-to-Parquet processing with DuckDB.
