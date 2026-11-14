# Historical project journal through Session 023

This is the former root README, preserved as a session-era record. Its plans,
credentials, and status statements describe their original context; use the
[current project README](README.md) for setup and current scope.

**Current phase note (2026-11-11):** The owner marked Phase 1 complete and opened
the [Review and Improvement Phase](docs/review-phase/ROADMAP.md). Phase 2 has not
started. Earlier references below to a pending Session 024 are historical plans.

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

The full platform runs locally with Docker Compose. Separate Terraform and
Kubernetes API learning labs were verified in Sessions 018-019. Kafka, Spark,
authentication, and a web UI remain deferred.

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

Session 018 revised the target to a **local, no-cloud-budget learning simulation**.
The user prioritizes understanding and simulation over production efficiency or
a large environment. After Session 018, provisionally **1-3 sessions remain**,
targeting Sessions 019-021 for this revised milestone. Setup and verification may
affect this estimate. Recovery and final Grafana visuals remain deferred.

| Session | Practical outcome |
|---------|-------------------|
| 015 | Separate run creation from execution, handle queued runs, and verify the lifecycle. |
| 016 | Add RabbitMQ and a worker; verify asynchronous submission and processing. |
| 017 | Verified terminal duplicates, continuation after failure, and queued work across worker downtime; mid-processing recovery deferred. |
| 018 | Completed local Terraform lifecycle exercises, source-built API deployment, database connectivity, and source-change detection. |
| 019 | Completed Kubernetes API, Secret, Pod replacement, storage, and cleanup exercises. |
| 020 | Implemented and verified dataset queries and persistent saved query tables. |
| 021 | Implemented and verified original CSV, processing-output Parquet, and saved-table Parquet downloads. |
| 022 | Implemented and verified full bounded query-result CSV exports from runs and saved tables. |
| 023 | Verified Terraform API replacement, health/database connectivity, convergence, and reviewed CI responsibilities. |
| 024 | Final closure review: reproduction prerequisites, retained resources, and deliberate cleanup decisions. |

The queue-and-worker milestone targets three sessions including Session 015;
two were considered possible if integration went smoothly. Learn related deployment
concepts together through this platform rather than assigning each a separate session.
Record documentation and verification as we go.

**Revised Phase 1 finish line:** a local learning deployment that the user
understands and can reproduce, with basic configuration, access/storage concepts,
and clear ownership. Infrastructure recreation does not restore data. Cloud
deployment and cloud IAM practice, production hardening, advanced Kubernetes,
comprehensive recovery, and durable event streaming remain later work.

Future sessions should continue from this agreed roadmap and the latest session
record. Discuss any necessary scope or estimate changes explicitly with the user.
Keep the learning-together workflow: explain each small task, wait for the user,
and only edit files or execute implementation steps when instructed. This roadmap
does not authorize implementing future tasks automatically.

## Documentation

- [Original study notes](Platform_Engineering_Study_Notes.md)
- [Session records](docs/sessions/)

## Current status

**Session 023 completed on 2026-11-10.** The user rebuilt the Terraform API lab,
confirmed both health endpoints, and confirmed a subsequent no-change plan.
The existing GitHub Actions run was reported green; its commit and test count
were not confirmed. No new pytest run was performed in this session.
One planned closure session remains (024); Phase 1 is not yet declared complete.
See [Session 023](docs/sessions/023-deployment-wrap-up.md).

**The three-session backend feature extension (020-022) is complete.** The platform
supports query previews, persistent derived tables, stored-file downloads, and CSV
query-result exports. Session 022 passed 200 automated tests and live CSV exports
from the user's four-customer demo and saved summary. See [the query guide](docs/query-tables.md).
The Compose API was rebuilt in Session 022. Phase 1 now
has one planned closure session (024); GUI, LAN verification,
and cross-file joins remain separate later work.

Separate close records:

- [020: queries and saved tables](docs/sessions/020-query-and-saved-tables.md):
  migration 004, restricted query execution, persistent tables, and the guided
  upload/process/query/compare/save/re-query demo. Test milestone: 140 passed.
- [021: stored-file downloads](docs/sessions/021-stored-file-downloads.md):
  original CSV and processing/saved-table Parquet downloads; the user verified the
  downloaded summary locally. Test milestones: 149, then 176 passed.
- [022: CSV query-result export](docs/sessions/022-csv-query-export.md):
  full bounded exports from processing runs and saved tables. Final suite:
  200 passed, including a post-formatting run at close.

The demo's new sample had four customers totaling 650; the prior Session 13 sample
had three totaling 415.75. The user saved and re-queried the new summary, then
downloaded it as Parquet. CSV exports were also independently parsed and checked.
These are synthetic sample comparisons, not a cross-file SQL join or business trend.

At session close, the user authorized the assistant to commit and push the combined
018-022 work to origin/main. Generated artifacts/
downloads stay local and are ignored; the source sample CSV and verification script
are included with the code and separate session records in the publication scope.

Session 019 completed the local Kubernetes exercises on Docker Desktop kind
v1.36.1. The user verified API health through localhost:8090 port-forwarding,
automatic Pod replacement, and database connectivity using a Secret. PostgreSQL
remains in Compose. A PVC exercise proved file survival across Pod recreation;
the practice Pod, claim, and backing volume were then deleted.

The API Deployment, Service, and platform-db Secret were retained. Browser access
requires a running port-forward. Full processing dependencies are not configured
in this Kubernetes lab. ConfigMaps were explained but not exercised. The Compose
worker is now running and processed the Session 020 smoke-test upload. The
Kubernetes and Terraform lab images were not refreshed in Session 020.

Next: final local deployment closure review in Session 024.
This user-requested order supersedes the earlier deployment-first target.
Phase 1 has not been declared complete.
See [Kubernetes exercises](kubernetes/README.md),
[Session 019](docs/sessions/019-local-kubernetes.md), and
[Terraform exercises](Terraform/README.md).

## Requested backend workflow: Sessions 020-022

Session 019 clarified the desired simulation: a second computer on the same LAN
uploads a CSV, queries a table derived from it, and downloads query results as
CSV. Session 020 added dataset SQL queries and persistent derived tables.
Session 021 added stored-file downloads and Session 022 added CSV result downloads.
LAN verification and a custom GUI remain pending.

On 2026-09-11, the user replaced the provisional 3-5-session estimate with
**three backend sessions, one per feature, before the remaining deployment work**.
The corrected numbering is 020, 021, and 022 because Session 019 already completed
the Kubernetes exercises. Sessions 020-022 are implemented and verified.

| Session | Feature and planned outcome |
|--------------------|-----------------------------|
| 020 | Verified bounded SQL previews, saving results as named Parquet tables, catalog lookup/listing, and querying/deriving saved tables. |
| 021 | Verified downloads of original uploaded CSV, processing-output Parquet, and saved-table Parquet. |
| 022 | Verified CSV query-result downloads, reusing restricted execution and full-result export limits. |

Use a hybrid learning workflow for these three sessions: the assistant explains
and performs one small task, the user observes and reviews, and both pause before
moving to the next task. This records the chosen mode; implementation starts only
when the user proceeds with that task. Session-start preparation remains
explanation-only apart from explicitly requested documentation edits.

The scope assumes small files, one selected dataset per query, bounded query
execution/results, and initial verification through /docs or an HTTP client.
The GUI comes later. LAN access remains pending and must be scoped separately;
multi-user access, cross-dataset joins, and saved query history are deferred.

After Session 023, **one planned closure session remains (024)** for the expanded
local Phase 1 milestone. Review reproduction prerequisites and retained resources,
then agree any cleanup and the completion decision. This is a planning estimate,
not a claim that Phase 1 is complete. The GUI and other deferred work follow later.

## Future replication and backup work

Requested in Session 023; planned for later, not implemented:

- Study service/data replication for availability and its failure boundaries.
- Plan PostgreSQL metadata and MinIO object backups, retention, and storage location.
- Practise restoring both stores together and verify that saved-table metadata
  resolves to readable files and correct query results.
- Distinguish replication from historical backups: accidental deletion or
  corruption can propagate to replicas. Infrastructure recreation alone does
  not restore data. Scope and session estimates will be agreed separately.

## Recent activity (2026-09-09 through 2026-09-11, Session 019)

- Prepared a local kind cluster and imported the Terraform lab image into its node.
- Verified API health, replacement Pods, Secret-based database access, and storage.
- Deleted practice storage after verifying persistence; retained API resources.
- Recorded reproduction guidance and future query/CSV/LAN requirements.
- No application behavior changes, pytest run, commit, or push at session close.

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

## Recent activity (2026-09-09, Session 018)

- Agreed a local learning simulation with no cloud budget.
- Practised Terraform initialization, planning, creation, replacement, and cleanup.
- Built/deployed our API through Terraform and verified PostgreSQL connectivity.
- Added seven source-hash triggers; verified change detection and return to no changes.
- Added Git exclusions and reproduction guidance; no commit/push or new pytest run.
- See [Session 018](docs/sessions/018-local-terraform.md) for the full record.

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
