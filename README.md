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

## Current local architecture

```text
User -> FastAPI -> PostgreSQL metadata
                 -> RabbitMQ -> Python worker -> MinIO -> DuckDB -> Parquet
API and worker -> /metrics -> Prometheus -> Grafana
```

The platform runs locally with Docker Compose. Kubernetes, Terraform,
Kafka, Spark, authentication, and a web UI are intentionally deferred until the
basic platform works reliably.

## Post-MVP direction

After the synchronous MVP is reliable, evolve processing in two stages:

1. Introduce a lightweight message queue and worker so processing can run
   asynchronously while PostgreSQL remains the source of truth for run state.
2. Introduce durable event streaming when several independent platform
   components need to react to events such as `upload.stored`,
   `processing.succeeded`, and `processing.failed`.

RabbitMQ now distributes processing jobs. Kafka or a
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
- [x] 012 - Add Grafana dashboards and basic alerting.
- [x] Post-MVP - Integrate asynchronous processing and verify basic queue reliability (Sessions 015-017; mid-processing recovery remains deferred).
- [ ] Post-MVP - Publish durable platform events for independent consumers.

## Remaining Phase 1 roadmap

Agreed at the start of Session 015 (2026-09-08): plan for **5-7 more sessions,
including Session 015**, at a similar length to recent sessions. This replaces
the earlier 12-18-session estimate. These are planned outcomes, not completed work
or guaranteed deadlines.

After Session 017, **2-4 sessions remain**, targeting completion in Sessions
019-021. Basic queue reliability is verified. Interrupted-running-run recovery
and final Grafana visual verification were explicitly deferred by the user.

| Session | Practical outcome |
|---------|-------------------|
| 015 | Separate run creation from execution, handle queued runs, and verify the lifecycle. |
| 016 | Add RabbitMQ and a worker; verify asynchronous submission and processing. |
| 017 | Verified terminal duplicates, continuation after failure, and queued work across worker downtime; mid-processing recovery deferred. |
| 018 | Use Terraform to provision a small cloud environment, covering networking, IAM, and secrets as we use them. |
| 019 | Deploy the platform to Kubernetes; learn configuration, services, and persistent storage through that deployment. |
| 020-021, if needed | Resolve deployment issues, connect CI deployment, and verify recreation and cleanup. |

The queue-and-worker milestone targets three sessions including Session 015;
two may be possible if integration goes smoothly. Learn related cloud concepts
together through this platform rather than assigning each a separate session.
Record documentation and verification as we go.

**Phase 1 finish line:** a working learning deployment that the user understands
and can reproduce, including its access controls and persistent data. Production
hardening, advanced Kubernetes, comprehensive disaster recovery, and durable event
streaming remain later work. Select the cloud provider and deployment details
together when approaching the cloud work.

Future sessions should continue from this agreed roadmap and the latest session
record. Discuss any necessary scope or estimate changes explicitly with the user.
Keep the learning-together workflow: explain each small task, wait for the user,
and only edit files or execute implementation steps when instructed. This roadmap
does not authorize implementing future tasks automatically.

## Documentation

- [Original study notes](Platform_Engineering_Study_Notes.md)
- [Session records](docs/sessions/)

## Current status

Session 017 added terminal-run duplicate handling and acknowledgment of recorded
terminal outcomes after ProcessingError. The user reported 96 passing tests and
verified live failure followed by success, duplicate delivery without changed
run timestamps, and queued work completing after worker startup. Next is Session
018: select cloud/deployment details and begin Terraform. Confirm the worker is
running first: it was stopped for a cancelled exercise and its final restart
was requested but not confirmed. See the Session 017 record for limitations.

## Queued-run preparation

`processing_runs` supports `queued`, `running`, `succeeded`, and `failed`.
`created_at` records submission time; `started_at` remains empty while queued.
Database constraints enforce consistent timestamps, results, and validation
fields. The API creates `queued` records; claiming sets `running` and the start
time together, only when the record is still queued. The run-read API exposes
`created_at` and allows a null `started_at`.

Migration `db/migrations/003_add_queued_processing_runs.sql` upgrades an existing
database once. It backfills historical `created_at` values from `started_at`.
Fresh databases use the updated `db/init.sql`; restarting a populated PostgreSQL
volume does not rerun initialization. The local migration was applied in
Session 014 and must not be reapplied there.

`process_upload()` translates `ProcessingError` categories into HTTP responses.
`submit_processing(upload_id, correlation_id)` validates the upload, creates a
queued run, and publishes its ID and correlation ID. `execute_processing(run_id,
correlation_id)` claims that existing run, resolves its upload, and processes it
without an HTTP request object or creating another run. The worker calls this
function; the endpoint returns HTTP 202 with `run_id` and initial `queued` status.
Read `GET /processing-runs/{run_id}` for current state and results.

Publishing uses Pika 1.3.2, a durable queue, persistent messages, publisher
confirmations, and mandatory routing. HTTP 503 on an unconfirmed submission
includes the run ID and preserves its state: delivery may be uncertain. Database
creation and publishing are not atomic; no outbox or automatic recovery exists.

The worker consumes one unacknowledged message at a time. It acknowledges after
success and skips already-succeeded/failed runs after a refused atomic claim.
After ProcessingError, it rereads PostgreSQL and acknowledges only a confirmed
terminal state. Missing/nonterminal runs, failed lookups, and unexpected errors
remain unacknowledged and stop consumption. Malformed messages are rejected
without requeueing (currently discarded). Message IDs do not deduplicate work;
the conditional claim and stored terminal state control duplicate handling.

A worker interrupted after claiming can leave a run stuck at running. Restarting
alone cannot recover that run. There are no leases, automatic retries, or stuck-run
recovery tooling. Manual recovery was discussed but not implemented or exercised.
Worker downtime before claiming was verified; mid-processing crash recovery was
explicitly deferred. These are limits of the current learning milestone.

RabbitMQ's management UI is at `http://localhost:15672`. The API and worker use
the internal `rabbitmq:5672` address. The image follows `rabbitmq:4-management`,
not an exact patch version; the session dashboard displayed RabbitMQ 4.3.5.

## Grafana and alerting

Grafana is available locally at `http://localhost:3000` after running
`docker compose up -d`. Its Prometheus data source and `Data Platform
Operations` dashboard are provisioned from files in `grafana/`.

Prometheus evaluates two initial alert rules:

- `PlatformProcessingInfrastructureFailure` detects recent storage or internal
  processing failures.
- `ApiHighMemoryUsage` detects API process memory above 256 MiB for five
  minutes.

These rules expose alert state in Prometheus and Grafana. External notification
delivery is deferred until an Alertmanager or Grafana contact point is added.

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
It also scrapes `http://worker:8001/metrics` with `job="worker"`. Processing
metrics now update in the worker's registry and reset when that process restarts.
PostgreSQL remains the durable run history.

The dashboard now selects the latest positive success timestamp across
processes and uses recent worker histogram rates for processing duration. The
memory panel's data-source UID trailing space was removed. Final dashboard
visual verification was skipped. The existing infrastructure alert includes
worker outcomes; API resource panels and the memory alert remain API-specific.

The application exposes these custom metrics:

- `platform_processing_runs_total{outcome=...}` counts successful, validation,
  storage, and internal outcomes.
- `platform_processing_duration_seconds{outcome=...}` measures processing time.
- `platform_processed_rows_total` counts rows from successful runs.
- `platform_last_successful_processing_timestamp_seconds` records the most
  recent successful completion time.

## Recent activity (2026-09-09, Session 017)

- Added safe acknowledgment of terminal duplicates and recorded processing failures.
- Expanded automated coverage from 76 to 96 passing tests, reported by the user.
- Verified failure followed by valid three-row processing without worker restart.
- Republished a succeeded run; verified an empty queue and unchanged timestamps.
- Verified queued work waited with zero consumers and completed after worker startup.
- Deferred mid-processing interruption/recovery and final Grafana visual checks.
- See [Session 017](docs/sessions/017-queue-reliability.md) for evidence and follow-up.

## Recent activity (2026-09-09, Session 016)

- Added RabbitMQ, confirmed publishing, HTTP 202 submission, and a separate worker.
- Verified the same run ID reached succeeded with three rows and was acknowledged.
- Adapted six execution tests and added 25 queue-related cases: 76 tests pass.
- Exposed worker metrics and verified a successful-run counter of 1 in Prometheus.
- Updated dashboard queries; final visual verification remains pending.
- See [Session 016](docs/sessions/016-rabbitmq-worker.md) for evidence and limitations.

## Recent activity (2026-09-08, Session 015)

- Recorded the agreed remaining Phase 1 roadmap: 5-7 sessions including 015.
- Made queued runs readable with submission timestamps and null start times.
- Separated queued-run creation, conditional claiming, and execution by run ID.
- Expanded the suite from 43 to 51 passing tests, as reported by the user.
- Verified live three-row processing and refusal to reclaim the completed run.
- See [Session 015](docs/sessions/015-run-submission-and-execution.md) for the
  walkthrough, evidence, limitations, and next checkpoint.

## Recent activity (2026-09-08, Session 014)

- Added queued-run constraints and separate submission/start timestamps.
- Applied migration 003, preserving nine existing processing runs.
- Verified acceptance of a valid queued row and rejection of an invalid one;
  both checks were rolled back.
- Extracted processing execution and centralized HTTP error translation.
- Preserved 43 passing tests and verified live three-row processing.
- See [Session 014](docs/sessions/014-queued-run-preparation.md) for decisions,
  verification, and remaining work.

## Recent activity (2026-09-06, Session 013)

- Added Grafana with persistent storage and file-based provisioning.
- Added a seven-panel operational dashboard for processing and API resources.
- Added Prometheus alerts for infrastructure failures and sustained memory use.
- Rejected cAdvisor after verifying that Docker Desktop exposed only broad
  WSL2 control groups rather than reliable Compose-service labels.
- Verified a successful run and a firing infrastructure alert through a
  controlled MinIO outage.
- Re-ran the automated suite with 43 passing tests.

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
