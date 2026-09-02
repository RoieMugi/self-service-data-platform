# Data Platform Engineering Journey

This repository is a hands-on learning project for moving from data engineering
into data platform engineering.

## Project goal

Build a small self-service batch data platform that lets a data engineer:

1. Register a CSV dataset through an API.
2. Trigger a processing run.
3. Store raw data in S3-compatible object storage.
4. Validate and transform the data.
5. Produce a curated Parquet dataset.
6. Inspect run status, row counts, and failures.

## MVP architecture

```text
User -> FastAPI -> PostgreSQL metadata
                 -> Python worker -> MinIO -> DuckDB -> Parquet
                 -> /metrics -> Prometheus time-series storage
```

The first version will run locally with Docker Compose. Kubernetes, Terraform,
Kafka, Spark, authentication, and a web UI are intentionally deferred until the
basic platform works reliably.

## Post-MVP direction

After the synchronous MVP is reliable, evolve processing in two stages:

1. Introduce a lightweight message queue and worker so processing can run
   asynchronously while PostgreSQL remains the source of truth for run state.
2. Introduce durable event streaming when several independent platform
   components need to react to events such as `upload.stored`,
   `processing.succeeded`, and `processing.failed`.

RabbitMQ is a candidate for distributing processing jobs. Kafka or a
Kafka-compatible platform such as Redpanda is a candidate for replayable event
streams. The final choice will be made when the platform has concrete consumers
such as data quality, lineage, catalog, metrics, or notifications.

## How we will work

- Build one small, testable increment at a time.
- Explain why each component exists before adding it.
- Keep session records in `docs/sessions/`.
- Record decisions, verification results, and the next checkpoint.
- Prefer a working vertical slice over collecting unrelated technologies.

## Checkpoints

- [x] 001 - Define the MVP and establish the project/session record.
- [x] 002 - Add a minimal FastAPI service with a health endpoint.
- [x] 003 - Containerize the API.
- [x] 004 - Add PostgreSQL and Docker Compose health checks.
- [x] 005 - Register datasets and persist metadata.
- [x] 006 - Add MinIO raw object storage.
- [x] 007 - Execute CSV-to-Parquet processing with DuckDB.
- [x] 008 - Track runs, validation results, and failures.
- [x] 009 - Add automated tests and GitHub Actions.
- [x] 010 - Add basic operational metrics and documentation.
- [x] 011 - Add structured logging and correlation identifiers.
- [ ] Post-MVP - Move processing to an asynchronous worker and job queue.
- [ ] Post-MVP - Publish durable platform events for independent consumers.

## Documentation

- [Original study notes](Platform_Engineering_Study_Notes.md)
- [Session records](docs/sessions/)

## Current status

Checkpoint 011 is complete. FastAPI now emits structured JSON request and
processing lifecycle logs, and propagates validated correlation identifiers
through response headers and diagnostic events. The automated suite contains 43
passing tests. The proposed next increment is Grafana dashboards and basic
alerting over the existing Prometheus metrics.

## Structured logging

Clients may send a UUID in the `X-Correlation-ID` request header. The API reuses
a valid value, generates a UUID when the header is absent or invalid, and returns
the effective value in the response header.

Request-completion logs include the correlation ID, HTTP method, stable route
template, status code, and duration. Processing events add upload and run IDs,
controlled outcomes, and successful row counts where relevant. CSV contents,
credentials, and request bodies are not logged.

## Operational metrics

Prometheus is available locally at `http://localhost:9090` after running
`docker compose up -d --build`. It scrapes `http://api:8000/metrics` inside the
Compose network and stores its time series in the `prometheus_data` volume.

The application exposes these custom metrics:

- `platform_processing_runs_total{outcome=...}` counts successful, validation,
  storage, and internal outcomes.
- `platform_processing_duration_seconds{outcome=...}` measures processing time.
- `platform_processed_rows_total` counts rows from successful runs.
- `platform_last_successful_processing_timestamp_seconds` records the most
  recent successful completion time.

## Recent activity (2026-09-02, Session 012)

- Added validated or generated request correlation identifiers.
- Added structured JSON request-completion and processing lifecycle logs.
- Covered success, validation, storage, and internal processing outcomes.
- Verified a correlated validation failure against the Dockerized API.
- Expanded the automated suite from 33 to 43 passing tests.

## Recent activity (2026-09-02, Session 011)

- Added a Prometheus-compatible FastAPI metrics endpoint.
- Instrumented processing outcomes, duration, row volume, and last success time.
- Added a pinned Prometheus server to Docker Compose with persistent storage.
- Verified Prometheus scraping and live successful and validation-failed runs.
- Expanded the automated suite from 27 to 33 passing tests.

## Recent activity (2026-09-01, Session 010)

- Added a GitHub Actions workflow for pushes and pull requests involving `main`.
- Matched CI to the project runtime with Python 3.11 and pinned dependencies.
- Verified 27 tests locally and in GitHub Actions run `#1`.
- Designed a required-check ruleset, but confirmed GitHub does not enforce it
  for this private repository on the current account plan.

## Recent activity (2026-09-01, Session 009)

- Added persistent processing-run lifecycle tracking in PostgreSQL.
- Added database-enforced state and validation constraints.
- Added `GET /processing-runs/{run_id}` for durable result inspection.
- Verified successful and validation-failed runs against live services.
- Expanded the automated suite to 27 passing tests.

## Recent activity (2026-08-31, Session 008)

- Added synchronous `POST /uploads/{upload_id}/process` processing with DuckDB.
- Added a curated MinIO data zone organized by dataset and upload UUIDs.
- Added UTF-8 BOM and mixed-line-ending handling discovered through live data.
- Verified the stored Parquet contents and expanded the suite to 20 tests.

## Recent activity (2026-08-26, Session 007)

- Added persistent MinIO object storage and an idempotent `raw` bucket initializer.
- Added `POST /datasets/{dataset_id}/uploads` with CSV and size validation.
- Added upload metadata persistence and compensating cleanup for partial failures.
- Verified a live upload in MinIO and PostgreSQL and expanded the suite to 12 tests.

## Recent activity (2026-08-25, Session 006)

- Added the PostgreSQL `datasets` schema and Docker Compose initialization mount.
- Added `POST /datasets` with validated request and response models.
- Verified real database persistence, duplicate protection, and invalid-input
  handling.
- Expanded the automated suite to 6 passing tests.

## Recent activity (2026-08-25)

- Established the first Git baseline for Checkpoints 001-004.
- Verified the baseline with 3 passing automated tests.
- Published `main` to the private GitHub repository
  `RoieMugi/self-service-data-platform`.
- Recorded the version-control work as Session 005 while keeping product
  checkpoint numbering separate from session numbering.

## Recent activity (2026-08-20)

- Created `/memories/repo/session_start_skill.md` — repository-scoped session-start checklist for assistant behavior.
- Created `/memories/repo/project_skill.md` — project-specific skill with "Learning together" rules and session-start phrases.
