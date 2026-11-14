# Learning Journey Timeline

**Current phase note (2026-11-11):** The owner marked Phase 1 complete and opened
the [Review and Improvement Phase](../review-phase/ROADMAP.md). Phase 2 has not
started. The Session 024 plan below records an earlier intention.

**Review R01 (2026-11-14):** New processing runs now write to run-specific
Parquet keys. The owner reported 201 passing tests and live verification of
two separately downloadable runs plus a readable legacy run. See the
[R01 record](../review-phase/R01-run-artifacts.md).

## Progress Overview

**Latest, Session 023 (2026-11-10):** reviewed deployment ownership and CI;
the user replaced the Terraform API image/container, verified API/database health,
and confirmed a no-change plan. Existing CI was reported green; no new pytest run.
One planned closure session remains (024). Replication and PostgreSQL/MinIO backup
and restore practice were added to future scope. Phase 1 is not yet complete.
See [Session 023](023-deployment-wrap-up.md).

All sessions are recorded in `docs/sessions/`. This timeline tracks what was built, when, and why.

**Sessions 021-022 (2026-09-14):** stored-file downloads and CSV query-result
exports are implemented and live-verified; 200 tests pass. The backend feature
extension is complete. Next: local deployment wrap-up in 023-024 if needed.
See [021](021-stored-file-downloads.md) and [022](022-csv-query-export.md).

**Session 020 (2026-09-14):** query previews and persistent saved tables
implemented and verified with 140 passing tests and a live Compose workflow.
Saved data survived API restart. See [Session 020](020-query-and-saved-tables.md).
This supersedes older forward-looking estimates: downloads are 021-022, then
deployment wrap-up in 023-024 if needed.

---

## **Session 001: Project Foundation**
**Date:** 2026-08-10  
**Status:** ✅ Complete

**What:** Defined the MVP architecture and project structure.

**Key decisions:**
- Self-service batch data platform as the goal
- Vertical slice: Register CSV → store → transform → output Parquet
- Initial stack: FastAPI, PostgreSQL, MinIO, DuckDB, Python, Docker Compose
- Deferred: Kubernetes, Terraform, Kafka, Spark, auth, frontend, AI

**Deliverables:**
- README with MVP, architecture, checkpoints
- Checkpoint structure for reproducible learning
- Session recording convention

**Why it matters:** Establishes the vision and prevents scope creep.

**Next:** Build the first working piece—the API.

---

## **Session 002: Minimal FastAPI Service**
**Date:** 2026-08-19  
**Status:** ✅ Complete

**What:** Built a working FastAPI app with one endpoint.

**Key features:**
- `GET /health` endpoint returning `{"status": "healthy"}`
- Automated tests with pytest
- Local server with uvicorn
- Live verification with curl

**Files created:**
- `app/main.py` — FastAPI application
- `app/__init__.py` — Python package marker
- `requirements.txt` — pinned dependencies
- `test_health.py` — automated tests

**Concepts learned:**
- HTTP routes and decorators
- Dependency pinning
- TestClient for isolated testing
- uvicorn as the ASGI server

**Why it matters:** Proves the framework works locally and establishes a pattern for all future endpoints.

**Next:** Package it for deployment.

---

## **Session 003: Containerize the API**
**Date:** 2026-08-20  
**Status:** ✅ Complete

**What:** Packaged the FastAPI service into a Docker image.

**Key achievements:**
- Created Dockerfile with Python 3.11-slim base
- Built image: `docker build -t data-platform-api:v1 .`
- Ran container: `docker run -p 8000:8000 data-platform-api:v1`
- Verified `/health` works inside container

**Environment blockers resolved:**
- Docker Desktop failed with "Virtualization support not detected"
- Root cause: WSL2 not installed
- Solution: Enabled WSL2 in Windows features
- Result: Docker engine started successfully

**Concepts learned:**
- Docker images vs containers
- Dockerfile layering and caching
- Docker build and run workflow
- WSL2 as Docker's Linux foundation on Windows
- Port mapping (`-p`)

**Why it matters:** Containerization is the foundation for orchestration, CI/CD, and reproducible deployments.

**Next:** Orchestrate multiple services with Docker Compose.
 
---

## **Session 004: Docker Compose and PostgreSQL**
**Date:** 2026-08-24  
**Status:** Complete

**What:** Added PostgreSQL and ran it together with FastAPI under Docker Compose.

**Key achievements:**
- Added PostgreSQL 15 with persistent storage and a readiness health check
- Connected FastAPI through Compose service networking
- Added `/db-health` with safe failure responses
- Verified success, database failure, and recovery behavior
- Added three automated endpoint tests
- Aligned local development with Python 3.11 in a project virtual environment

**Why it matters:** The platform now has its first persistent dependency and can
distinguish application health from database connectivity.

**Next:** Register datasets and persist their metadata in PostgreSQL.

---

## **Session 005: Git and GitHub Baseline**

**Date:** 2026-08-25
**Status:** Complete

**What:** Created the first Git commit for the completed platform foundation and
published the `main` branch to a private GitHub repository.

**Key achievements:**
- Reviewed Git and Docker ignore rules
- Verified all 3 automated tests before committing
- Created a known-good baseline for Checkpoints 001-004
- Connected the local repository to GitHub and configured `origin/main`

**Why it matters:** The project now has durable version history, an off-machine
copy, and a safe baseline for the next engineering increment.

**Next:** Begin product Checkpoint 005: register datasets and persist metadata.

---

## **Session 006: Dataset Registration**

**Date:** 2026-08-25
**Status:** Complete

**What:** Added the first platform metadata resource and persisted it in
PostgreSQL.

**Key achievements:**
- Added the `datasets` table with generated UUIDs and timestamps
- Added `POST /datasets` with input validation
- Returned HTTP 409 for duplicate names and HTTP 422 for invalid names
- Verified the real API-to-PostgreSQL path
- Expanded the automated suite to 6 passing tests

**Why it matters:** The platform now has a stable logical identity for each
dataset. Future CSV uploads, processing runs, and curated outputs can reference
that identity instead of depending on filenames.

**Next:** Add MinIO and associate uploaded CSV objects with registered datasets.

---

## **Session 007: MinIO Raw Object Storage**

**Date:** 2026-08-26
**Status:** Complete

**What:** Added persistent raw CSV storage and connected uploads to registered
datasets.

**Key achievements:**
- Added MinIO and an idempotent `raw` bucket initializer to Docker Compose
- Added the `uploads` metadata table and dataset relationship
- Added `POST /datasets/{dataset_id}/uploads`
- Added CSV validation and compensating cleanup for partial failures
- Verified a live upload in MinIO and PostgreSQL
- Expanded the automated suite to 12 passing tests

**Why it matters:** The platform now owns both logical dataset metadata and the
physical raw files associated with it, completing the ingestion boundary needed
before processing can begin.

**Next:** Transform uploaded CSV objects into curated Parquet with DuckDB.

---

## **Session 008: DuckDB CSV-to-Parquet Processing**

**Date:** 2026-08-31
**Status:** Complete

**What:** Added the platform's first processing path from raw CSV to curated
Parquet.

**Key achievements:**
- Added a curated MinIO bucket and explicit raw/curated configuration
- Added `POST /uploads/{upload_id}/process`
- Used PostgreSQL metadata to resolve raw MinIO objects
- Converted CSV to Parquet synchronously with DuckDB
- Returned curated object metadata and row counts
- Handled UTF-8 BOM and mixed-line-ending input found during live verification
- Verified the stored Parquet object and its three source rows
- Expanded the automated suite to 20 passing tests

**Why it matters:** The platform now does more than register and store data. It
can turn a managed raw upload into an analytics-ready curated artifact, completing
the core MVP transformation path.

**Next:** Persist processing runs, validation outcomes, failures, and curated
output metadata.

---

## **Session 009: Processing Run and Validation Tracking**

**Date:** 2026-09-01
**Status:** Complete

**What:** Added durable processing-run history and validation outcomes.

**Key achievements:**
- Added database-enforced run states and validation constraints
- Added versioned migrations for the existing PostgreSQL database
- Tracked successful and failed processing attempts
- Added `GET /processing-runs/{run_id}`
- Verified success and validation failure against live services
- Expanded the automated suite to 27 passing tests

**Why it matters:** Processing is now inspectable after the original request.
Users can retrieve durable status, timing, output, validation, and failure data.

**Next:** Automate repository verification with GitHub Actions.

---

## **Session 010: Continuous Integration with GitHub Actions**

**Date:** 2026-09-01
**Status:** Complete

**What:** Added automatic test execution for repository integration events.

**Key achievements:**
- Added `.github/workflows/tests.yml`
- Triggered CI for pushes and pull requests involving `main`
- Used a clean Ubuntu runner with Python 3.11 and pip caching
- Installed pinned dependencies and ran the 27-test pytest suite
- Verified GitHub Actions run `#1` succeeded in 17 seconds
- Explored required status checks and documented the private-repository plan
  limitation

**Why it matters:** Test execution is now a repeatable repository process rather
than an optional local step. Every integration event receives independent
verification on a clean Linux runner.

**Next:** Add basic operational metrics and documentation.

---

## **Session 011: Operational Metrics with Prometheus**

**Date:** 2026-09-02
**Status:** Complete

**What:** Added application-level processing metrics and persistent local
collection with Prometheus.

**Key achievements:**
- Added `GET /metrics` using the Prometheus Python client
- Measured processing outcomes, duration, successful row volume, and latest
  successful completion time
- Kept metric labels low-cardinality with four controlled outcome values
- Added a pinned Prometheus service and persistent volume to Docker Compose
- Verified the `api:8000` scrape target and queried stored live samples
- Expanded the automated suite to 33 passing tests

**Why it matters:** Operators can now observe aggregate platform behavior over
time instead of inspecting only individual API responses and database records.

**Next:** Add structured logging and correlation identifiers so individual
requests and processing runs can be traced across diagnostic events.

---

## **Session 012: Structured Logging and Correlation IDs**

**Date:** 2026-09-02
**Status:** Complete

**What:** Added request correlation and machine-readable diagnostic events.

**Key achievements:**
- Validated caller-supplied correlation UUIDs and generated safe replacements
- Returned the effective correlation ID in response headers
- Added structured request-completion and processing lifecycle events
- Covered success, validation, storage, and internal processing outcomes
- Verified a live correlated validation failure against the Dockerized API
- Expanded the automated suite to 43 passing tests

**Why it matters:** Operators can trace one request and processing attempt across
diagnostic events and connect aggregate metrics to a specific durable run.

**Next:** Add Grafana dashboards and basic alerting over Prometheus metrics.

---

## **Session 013: Grafana Dashboard and Alerting**

**Date:** 2026-09-06
**Status:** Complete

**What:** Added a provisioned Grafana dashboard and Prometheus alert rules over
the platform's existing operational metrics.

**Key achievements:**
- Provisioned Grafana's Prometheus data source and seven-panel dashboard from
  version-controlled files
- Visualized processing outcomes, duration, row throughput, last success time,
  API CPU usage, and API memory usage
- Added alerts for storage/internal failures and sustained high memory
- Evaluated and rejected cAdvisor because Docker Desktop did not expose reliable
  per-Compose-service labels
- Verified a firing infrastructure alert through a controlled MinIO outage
- Preserved all 43 passing automated tests

**Why it matters:** Operators now have a durable visual overview and automatic
failure detection before processing is separated into an asynchronous worker.

**Next:** Introduce an asynchronous job queue and worker.

---

## **Session 014: Queued Runs and Processing Separation**

**Date:** 2026-09-08
**Status:** Complete for this preparation increment

**What:** Prepared the run schema for queued work and separated HTTP handling
from synchronous processing execution.

**Key achievements:**
- Applied migration 003 with submission timestamps and queued-state constraints
- Preserved nine historical runs and verified valid/invalid queued inserts
- Added explicit start timestamps to current synchronous run creation
- Extracted processing execution with correlation IDs and domain errors
- Preserved 43 passing tests and verified live three-row processing

**Why it matters:** The database can represent waiting jobs, and processing no
longer depends directly on HTTP requests or exceptions. Execution still happens
inside the API container and creates its own run.

**Next:** Separate run creation from execution before introducing the queue
and worker. See [Session 014](014-queued-run-preparation.md).

---

## **Session 015: Run Submission and Execution**

**Date:** 2026-09-08
**Status:** Complete for this increment; asynchronous deployment remains pending

**What:** Separated queued-run creation from execution of an existing run ID.

**Key achievements:**
- Exposed creation timestamps and nullable start timestamps through run lookup
- Added a conditional queued-to-running claim with an explicit start timestamp
- Split submission and execution while preserving synchronous HTTP behavior
- Expanded the automated suite to 51 passing tests, reported by the user
- Verified live processing of three rows and rejection of a completed-run claim
- Agreed a 5-7-session remaining Phase 1 roadmap, including Session 015

**Why it matters:** A future worker can execute an already submitted run without
creating a second record. PostgreSQL controls whether a queued run can start.

**Next:** Add RabbitMQ and a worker in Session 016. Follow the agreed roadmap in
the root README. See [Session 015](015-run-submission-and-execution.md).

---

## **Session 016: RabbitMQ and Asynchronous Worker**

**Date:** 2026-09-09
**Status:** Complete for integration; reliability remains Session 017 work

**What:** Moved processing into a separate RabbitMQ consumer with HTTP 202
submission, preserving the existing run ID and correlation context.

**Key achievements:**
- Added a durable queue, persistent messages, publisher confirmations, and a worker
- Verified live three-row processing and acknowledgment with one consumer remaining
- Adapted six execution tests and added 25 queue cases; the user verified 76 passing tests
- Exposed worker metrics on port 8001; verified Prometheus UP and success counter 1
- Updated dashboard aggregation/duration queries and corrected a data-source UID
- Recorded uncertain publication and duplicate/restart recovery as unfinished work

**Next:** Session 017 reliability checks. See [Session 016](016-rabbitmq-worker.md).
The roadmap leaves 3-5 sessions, targeting Phase 1 completion in 019-021.

---
## **Session 017: Queue Reliability**

**Date:** 2026-09-09
**Status:** Complete for agreed scope; mid-processing recovery deferred

**What:** Added terminal duplicate handling and acknowledgment after confirmed
terminal processing errors, preserving atomic claiming and durable run history.

**Key achievements:**
- User reported 96 passing automated tests, up from 76
- Verified a failed CSV run followed by successful three-row processing without restart
- Verified live duplicate acknowledgment with unchanged run timestamps
- Verified queued work with zero consumers completed after worker startup
- User deferred interrupted-running-run recovery and final Grafana visual checks

**Next:** Session 018 cloud selection and Terraform; 2-4 sessions remain, targeting
Phase 1 completion in 019-021. Confirm worker startup after the cancelled exercise.
See [Session 017](017-queue-reliability.md) for evidence and remaining limitations.

---
## **Session 018: Local Terraform Simulation**

**Date:** 2026-09-09
**Status:** Complete for local learning scope

**What:** Practised Terraform with Docker, then deployed our source-built API and
connected it to the existing Compose database.

**Key achievements:**
- Revised the cloud roadmap to a local simulation with no cloud budget
- Installed Terraform 1.15.8 and initialized Docker provider 4.6.0
- Verified Nginx creation, port-change replacement, and destruction
- Verified API health and PostgreSQL connectivity on localhost:8089
- Added source builds, seven file-hash triggers, and Git exclusions
- Verified a temporary source edit proposed replacement; reverted it without apply
- Final user-reported plan: no changes; no new pytest result

**Next:** Session 019 local Kubernetes. Provisionally 1-3 sessions remain for the
revised local milestone. See [Session 018](018-local-terraform.md).

---

## **Session 019: Local Kubernetes**

**Dates:** 2026-09-09 through 2026-09-11
**Status:** Complete for agreed learning scope

**What:** Ran our API in Docker Desktop kind v1.36.1, connected it to the
Compose database through a Secret, and practised persistent storage.

**Key achievements:**

- Resolved image availability by exporting/copying/importing into the node runtime
- Verified Deployment, Service, browser health, and automatic Pod replacement
- Verified Secret-injected database URL and successful /db-health
- Verified a 1Gi PVC preserved a file across standalone Pod recreation
- Deleted practice Pod/PVC and verified backing PV NotFound
- Discussed LAN user access, dataset queries, and CSV downloads as future work
- ConfigMaps remained conceptual; no new pytest result

**Next:** Review reproduction and local milestone wrap-up in Session 020.
Expanded query/CSV workflow estimate: 3-5 additional learning sessions, separate
from deployment wrap-up; implementation mode remains undecided.
See [Session 019](019-local-kubernetes.md) and [Kubernetes guide](../../kubernetes/README.md).

---

## **Completed Checkpoints**

| # | Checkpoint | Session | Date | Status |
|---|-----------|---------|------|--------|
| 001 | Project foundation | S001 | 2026-08-10 | ✅ Complete |
| 002 | Minimal FastAPI + health endpoint | S002 | 2026-08-19 | ✅ Complete |
| 003 | Containerize the API | S003 | 2026-08-20 | ✅ Complete |
| 004 | Docker Compose + PostgreSQL | S004 | 2026-08-24 | ✅ Complete |
| 005 | Register datasets & metadata | S006 | 2026-08-25 | ✅ Complete |
| 006 | MinIO raw object storage | S007 | 2026-08-26 | Complete |
| 007 | CSV-to-Parquet with DuckDB | S008 | 2026-08-31 | Complete |
| 008 | Track runs & validation | S009 | 2026-09-01 | Complete |
| 009 | Automated tests & GitHub Actions | S010 | 2026-09-01 | Complete |
| 010 | Observability & docs | S011 | 2026-09-02 | Complete |
| 011 | Structured logging and correlation IDs | S012 | 2026-09-02 | Complete |
| 012 | Grafana dashboards and basic alerting | S013 | 2026-09-06 | Complete |

---

## **Key Milestones**

✅ **Working vertical slice:** Users can call `GET /health` on a containerized FastAPI service.

✅ **Reproducible environment:** The Dockerfile and requirements.txt ensure consistent setup across machines.

✅ **Foundation for multi-service platform:** The API and PostgreSQL now run together under Docker Compose with health checks.

✅ **Raw ingestion path:** Registered datasets can receive CSV uploads whose bytes
are persisted in MinIO and whose metadata is tracked in PostgreSQL.

✅ **Curated processing path:** Raw CSV uploads can be transformed with DuckDB and
stored as dataset-organized Parquet objects in MinIO.

✅ **Operational visibility:** FastAPI exposes processing metrics that Prometheus
collects every 15 seconds into persistent local time-series storage.

---

## **Project State**

**Current codebase (main paths):**
```text
app/main.py          API, run lifecycle, and shared processing
app/messaging.py     RabbitMQ publisher and connection settings
app/worker.py        Consumer and worker metrics server
db/                  Initialization and migrations
Dockerfile           Shared API/worker image
docker-compose.yml   Local services
prometheus.yml       API and worker scraping
prometheus-alerts.yml
grafana/            Dashboard and provisioning (directory)
test_health.py       API and processing tests
test_messaging.py    Submission, publisher, and worker tests
docs/sessions/       Session history
```

**What works now:**
- Local FastAPI app with `/health` and `/db-health` endpoints
- PostgreSQL metadata storage under Docker Compose
- Dataset registration through `POST /datasets`
- Validation and duplicate-name protection
- Raw CSV storage and curated Parquet processing
- 200 automated tests passed by Session 022
- Bounded SQL previews, persistent saved tables, catalog lookup and derived tables
- Automatic pytest execution with GitHub Actions
- Docker image builds and runs
- Prometheus metrics collection with persistent Docker storage
- Structured JSON request and processing lifecycle logs
- Correlation IDs in response headers and diagnostic events
- Queued-run schema with submission and execution timestamps
- Separate HTTP wrapper, submission, and execution by existing run ID
- Conditional queued-to-running claiming and readable queued-run timestamps
- RabbitMQ publication, HTTP 202 submission, and a separate worker
- Worker metrics scraped by Prometheus; final dashboard visual check pending

**What's next:**
- Session 023 complete; final local deployment closure review remains in Session 024
- Local Terraform and Kubernetes API labs verified; Compose still owns the database
- Original local milestone target: 019-021; final wrap-up to review after 019
- Queries and saved tables verified; LAN and GUI remain future work
- Worker running and live processing verified in Session 020
- Interrupted-running-run recovery and final Grafana visual verification remain deferred
- Continue the agreed Phase 1 roadmap in the root README
- Later, add event streaming when
  multiple platform consumers need the same lifecycle events

---

## **Learning Path**

1. **Vertical slice** (sessions 1–3): Prove one simple feature works end-to-end
2. **Multi-service orchestration** (session 4): Add database, run together
3. **Data pipeline** (sessions 6–8): Implement registration, storage, and core ETL logic
4. **Run visibility** (session 9): Persist processing and validation outcomes
5. **Automation** (checkpoint 009): GitHub Actions and CI
6. **Observability** (checkpoints 010-011): Metrics, structured logs, and
   correlated diagnostics
7. **Visualization and alerting**: Grafana dashboards and basic alerts
8. **Event-driven evolution** (post-MVP): Add queued workers, then publish
   replayable platform events for quality, lineage, catalog, metrics, and
   notification consumers

---

**Last updated:** 2026-11-10 (Session 023 deployment wrap-up)
