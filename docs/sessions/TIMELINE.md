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

## **Completed Checkpoints**

| # | Checkpoint | Session | Date | Status |
|---|-----------|---------|------|--------|
| 001 | Project foundation | S001 | 2026-08-10 | ✅ Complete |
| 002 | Minimal FastAPI + health endpoint | S002 | 2026-08-19 | ✅ Complete |
| 003 | Containerize the API | S003 | 2026-08-20 | ✅ Complete |
| 004 | Docker Compose + PostgreSQL | S004 | 2026-08-24 | ✅ Complete |
| 005 | Register datasets & metadata | S006 | 2026-08-25 | ✅ Complete |
| 006 | MinIO raw object storage | - | - | 📋 Planned |
| 007 | CSV-to-Parquet with DuckDB | - | - | 📋 Planned |
| 008 | Track runs & validation | - | - | 📋 Planned |
| 009 | Automated tests & GitHub Actions | - | - | 📋 Planned |
| 010 | Observability & docs | - | - | 📋 Planned |

---

## **Key Milestones**

✅ **Working vertical slice:** Users can call `GET /health` on a containerized FastAPI service.

✅ **Reproducible environment:** The Dockerfile and requirements.txt ensure consistent setup across machines.

✅ **Foundation for multi-service platform:** The API and PostgreSQL now run together under Docker Compose with health checks.

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
- Six automated tests
- Docker image builds and runs

**What's next:**
- Add MinIO for raw object storage
- Upload CSV files against registered dataset IDs
- Add data transformation and run tracking

---

## **Learning Path**

1. **Vertical slice** (sessions 1–3): Prove one simple feature works end-to-end
2. **Multi-service orchestration** (session 4): Add database, run together
3. **Data pipeline** (sessions 6–8): Implement registration, storage, and core ETL logic
4. **Observability** (session 8): Add monitoring and logging
5. **Automation** (session 9): GitHub Actions, CI/CD
6. **Production readiness** (session 10+): Scale, optimize, document

---

**Last updated:** 2026-08-25 (Session 006)
