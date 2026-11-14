# Self-Service Batch Data Platform

A local data platform prototype for registering CSV datasets, processing them asynchronously, and querying or downloading curated results. It demonstrates API design, durable run metadata, object storage, a queue-backed worker, observability, and reproducible infrastructure labs.

## What it does

1. Register a dataset and upload a CSV through FastAPI.
2. Store the original file in MinIO and record metadata in PostgreSQL.
3. Submit a processing run to RabbitMQ; a separate worker validates the CSV and writes Parquet with DuckDB.
4. Read run status, preview bounded SQL queries, save derived tables, and download CSV or Parquet results.
5. Inspect JSON logs, Prometheus metrics, Grafana dashboards, and basic alert rules.

This is a **local learning system**. Its API has no user authentication, the included credentials are disposable demo values, and its SQL executor is not a public multi-user sandbox. Compose publishes its ports only on `127.0.0.1`.

## Architecture

```text
Client -> FastAPI -> PostgreSQL (dataset, run, and table metadata)
                  -> MinIO (raw CSV and curated Parquet)
                  -> RabbitMQ -> Python worker -> DuckDB -> MinIO
FastAPI + worker -> Prometheus -> Grafana
```

PostgreSQL is the source of truth for run state. RabbitMQ carries work requests; the worker claims a queued run before processing it. See [queue behavior and recovery limits](PROJECT_HISTORY.md#queued-run-preparation) and the [query guide](docs/query-tables.md) for implementation details.

## Quick start

Prerequisites: Docker with Compose and free local ports 5432, 8000, 9000, 9001, 9090, 3000, and 15672. Python 3.11 is needed for the optional smoke test and pytest. From the repository root in PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/db-health
```

Open [API docs](http://127.0.0.1:8000/docs), [Grafana](http://127.0.0.1:3000), or [Prometheus](http://127.0.0.1:9090). The MinIO console is at [localhost:9001](http://127.0.0.1:9001). Credentials are in your local `.env`, copied from [.env.example](.env.example). Do not reuse those values outside this disposable demo.

For a complete upload, process, query, and saved-table smoke test, install the test dependencies on the host and run:

```powershell
python -m pip install -r requirements-dev.txt
python scripts/verify_saved_tables.py
```

The smoke test creates and retains one sample dataset, run, and two saved tables. Run the automated suite with `python -m pytest -q`. CI runs that suite on pushes and pull requests to `main`.

Fresh PostgreSQL volumes are initialized by `db/init.sql`. Existing volumes are **not** reinitialized on `docker compose up`; apply only the migrations they still need from `db/migrations/`. Changing `.env` passwords does not rotate credentials already stored in PostgreSQL, RabbitMQ, MinIO, or Grafana volumes. Named volumes preserve local data across container replacement and are not backups.

## Current status and limits

The Compose workflow and backend features through Session 022 are implemented. Session 023 reproduced the separate Terraform API lab and reviewed CI. **The owner marked Phase 1 complete on 2026-11-11. The Review and Improvement Phase is now active; Phase 2 has not started.** The earlier plan for a Phase 1 Session 024 is superseded by the [review roadmap](docs/review-phase/ROADMAP.md). [R01](docs/review-phase/R01-run-artifacts.md) gave each new processing run its own Parquet key. The owner reported **201 passing tests** and live verification of two distinct, downloadable run artifacts plus a readable legacy artifact. These checks were not independently rerun in the assistant's shell.

The worker does not automatically recover a run interrupted after it was claimed. Database creation and queue publication are not atomic. The Terraform and Kubernetes directories are separate **API-only learning labs**, not deployments of the complete pipeline. Kubernetes' earlier host-port database connection is affected by the new loopback-only Compose binding; see its [updated lab guide](kubernetes/README.md) before reproducing it. LAN access, authentication, backup and restore, a web UI, and durable event streaming remain future work.

## Project records

- [Query, saved table, and download guide](docs/query-tables.md)
- [Review findings and improvement roadmap](docs/review-phase/ROADMAP.md)
- [Session index and verification records](docs/sessions/README.md)
- [Historical project journal and operational notes](PROJECT_HISTORY.md)
- [Terraform API lab](Terraform/README.md) and [Kubernetes API lab](kubernetes/README.md)
- [Original study notes](Platform_Engineering_Study_Notes.md)
