# Learning Journey Timeline

## Progress Overview

All sessions are recorded in `docs/sessions/`. This timeline tracks what was built, when, and why.

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

**Current codebase:**
```
data-platform-engineering/
├── app/
│   ├── __init__.py
│   └── main.py                    # FastAPI app
├── Dockerfile                     # Docker recipe
├── requirements.txt              # Dependencies
├── test_health.py                # Tests
├── README.md                     # Project overview
├── Platform_Engineering_Study_Notes.md
└── docs/
    └── sessions/
        ├── 001-project-foundation.md
        ├── 002-minimal-fastapi.md
        └── 003-containerize-api.md
```

**What works now:**
- Local FastAPI app with `/health` and `/db-health` endpoints
- PostgreSQL metadata storage under Docker Compose
- Dataset registration through `POST /datasets`
- Validation and duplicate-name protection
- Raw CSV storage and curated Parquet processing
- 33 automated tests
- Automatic pytest execution with GitHub Actions
- Docker image builds and runs
- Prometheus metrics collection with persistent Docker storage

**What's next:**
- Add structured logging and correlation identifiers
- Later, separate processing into a queued worker and add event streaming when
  multiple platform consumers need the same lifecycle events

---

## **Learning Path**

1. **Vertical slice** (sessions 1–3): Prove one simple feature works end-to-end
2. **Multi-service orchestration** (session 4): Add database, run together
3. **Data pipeline** (sessions 6–8): Implement registration, storage, and core ETL logic
4. **Run visibility** (session 9): Persist processing and validation outcomes
5. **Automation** (checkpoint 009): GitHub Actions and CI
6. **Observability** (checkpoint 010): Metrics and operational documentation
7. **Event-driven evolution** (post-MVP): Add queued workers, then publish
   replayable platform events for quality, lineage, catalog, metrics, and
   notification consumers

---

**Last updated:** 2026-09-02 (Session 011)
