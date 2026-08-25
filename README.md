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
```

The first version will run locally with Docker Compose. Kubernetes, Terraform,
Kafka, Spark, authentication, and a web UI are intentionally deferred until the
basic platform works reliably.

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
- [ ] 006 - Add MinIO raw object storage.
- [ ] 007 - Execute CSV-to-Parquet processing with DuckDB.
- [ ] 008 - Track runs, validation results, and failures.
- [ ] 009 - Add automated tests and GitHub Actions.
- [ ] 010 - Add basic operational metrics and documentation.

## Documentation

- [Original study notes](Platform_Engineering_Study_Notes.md)
- [Session records](docs/sessions/)

## Current status

Checkpoint 005 is complete. The platform can register logical datasets through
`POST /datasets` and persist their metadata in PostgreSQL with generated UUIDs,
timestamps, validation, and duplicate-name protection. The next engineering
increment is MinIO raw object storage and CSV uploads associated with registered
datasets.

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
