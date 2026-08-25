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

## **Completed Checkpoints**

| # | Checkpoint | Session | Date | Status |
|---|-----------|---------|------|--------|
| 001 | Project foundation | S001 | 2026-08-10 | ✅ Complete |
| 002 | Minimal FastAPI + health endpoint | S002 | 2026-08-19 | ✅ Complete |
| 003 | Containerize the API | S003 | 2026-08-20 | ✅ Complete |
| 004 | Docker Compose + PostgreSQL | S004 | 2026-08-24 | ✅ Complete |
| 005 | Register datasets & metadata | - | - | 📋 Planned |
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
- Local FastAPI app with `/health` endpoint
- Automated tests
- Docker image builds and runs
- Container responds to HTTP requests

**What's next:**
- Add PostgreSQL for metadata
- Use Docker Compose to orchestrate both services
- Implement dataset registration API
- Add data transformation pipeline

---

## **Learning Path**

1. **Vertical slice** (sessions 1–3): Prove one simple feature works end-to-end
2. **Multi-service orchestration** (session 4): Add database, run together
3. **Data pipeline** (sessions 5–7): Implement the core ETL logic
4. **Observability** (session 8): Add monitoring and logging
5. **Automation** (session 9): GitHub Actions, CI/CD
6. **Production readiness** (session 10+): Scale, optimize, document

---

**Last updated:** 2026-08-20
