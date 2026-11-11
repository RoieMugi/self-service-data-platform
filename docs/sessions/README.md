# Session Records

Each file records one working session or checkpoint. A record includes:

- the objective;
- concepts learned;
- decisions and tradeoffs;
- files changed;
- verification performed;
- blockers;
- the next small step.

These records are part of the project, not temporary notes.

---

## Sessions

| Session | Date | Checkpoint | Status |
|---------|------|------------|--------|
| [001](001-project-foundation.md) | 2026-08-10 | Define MVP and project structure | Complete |
| [002](002-minimal-fastapi.md) | 2026-08-19 | Minimal FastAPI with `/health` | Complete |
| [003](003-containerize-api.md) | 2026-08-20 | Containerize API with Docker | Complete |
| [004](004-compose-postgresql.md) | 2026-08-24 | Docker Compose and PostgreSQL | Complete |
| [005](005-git-github-baseline.md) | 2026-08-25 | Establish Git and GitHub baseline | Complete |
| [006](006-dataset-registration.md) | 2026-08-25 | Register datasets and persist metadata | Complete |
| [007](007-minio-raw-storage.md) | 2026-08-26 | Store CSV uploads in MinIO | Complete |
| [008](008-duckdb-csv-to-parquet.md) | 2026-08-31 | Convert raw CSV to curated Parquet | Complete |
| [009](009-processing-run-tracking.md) | 2026-09-01 | Track processing runs and validation | Complete |
| [010](010-continuous-integration.md) | 2026-09-01 | Automate tests with GitHub Actions | Complete |
| [011](011-operational-metrics.md) | 2026-09-02 | Add operational metrics with Prometheus | Complete |
| [012](012-structured-logging.md) | 2026-09-02 | Add structured logging and correlation IDs | Complete |
| [013](013-grafana-dashboard-alerting.md) | 2026-09-06 | Add Grafana dashboards and basic alerting | Complete |
| [014](014-queued-run-preparation.md) | 2026-09-08 | Prepare queued runs and separate HTTP from execution | Complete |
| [015](015-run-submission-and-execution.md) | 2026-09-08 | Separate queued-run submission, claiming, and execution | Complete |
| [016](016-rabbitmq-worker.md) | 2026-09-09 | RabbitMQ, asynchronous worker, and worker metrics | Integration complete; reliability pending |
| [017](017-queue-reliability.md) | 2026-09-09 | Terminal duplicates, recorded failures, and queued-worker restart behavior | Complete for agreed scope; mid-processing recovery deferred |
| [018](018-local-terraform.md) | 2026-09-09 | Local Terraform lifecycle, source-built API, database connection, and rebuild triggers | Complete for local learning scope |
| [019](019-local-kubernetes.md) | 2026-09-09 to 2026-09-11 | Local Kubernetes API, Secret, Pod replacement, storage and cleanup | Complete for agreed learning scope |
| [020](020-query-and-saved-tables.md) | 2026-09-11 to 2026-09-14 | Dataset queries, saved tables, and guided comparison demo | Complete |
| [021](021-stored-file-downloads.md) | 2026-09-14 | Original CSV, processing-output and saved-table downloads | Complete |
| [022](022-csv-query-export.md) | 2026-09-14 | Full bounded CSV query-result exports | Complete; backend feature extension finished |
| [023](023-deployment-wrap-up.md) | 2026-11-10 | Terraform API recreation, deployment ownership, and CI review | Complete; final Phase 1 closure review remains |

## Quick Links

Latest: [Session 023 - Local deployment wrap-up](023-deployment-wrap-up.md)
(2026-11-10): Terraform replacement and convergence verified; CI reviewed.
Final Phase 1 closure review remains Session 024.

- **[Learning Timeline](TIMELINE.md)** - Overview of all sessions and progress
- **[Project README](../../README.md)** - Overview, architecture, and quick start
- **[Study Notes](../../Platform_Engineering_Study_Notes.md)** - Background and career vision
