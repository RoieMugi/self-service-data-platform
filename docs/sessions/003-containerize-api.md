# Session 003 - Containerize the FastAPI API

**Date:** 2026-08-20  
**Status:** Complete

## Objective

Package the FastAPI application and all its dependencies into a Docker image that runs consistently anywhere. This checkpoint proves the service works in isolation and sets up for Docker Compose multi-service orchestration (Checkpoint 004).

## What we built

A **Dockerfile** that:
- Starts with Python 3.11-slim base image
- Copies the app code into the container
- Installs all dependencies
- Exposes port 8000
- Runs uvicorn at startup

## Concepts Learned

### What is Docker?

Docker packages your application and all its dependencies into a **container image**—a single, portable unit that runs the same way everywhere.

Without Docker:
- "Works on my machine" problems
- Manual environment setup on every deploy
- Different OS/Python/library versions cause failures

With Docker:
- One image runs identically on any machine with Docker
- Reproducible deployments
- Foundation for orchestration (Compose, Kubernetes)

### The Build Process

The `docker build` command reads the Dockerfile and:
1. Pulls the base Python image
2. Sets up the working directory
3. Copies project files into the container
4. Installs dependencies
5. Creates a snapshot (image) ready to run

### Layering & Caching

Docker builds images in layers. Each Dockerfile line creates a layer:
```
FROM python:3.11-slim    → Layer 1: base image
WORKDIR /app              → Layer 2: directory
COPY . .                  → Layer 3: files
RUN pip install ...       → Layer 4: dependencies
EXPOSE 8000              → Layer 5: port metadata
CMD [...]                → Layer 6: startup command
```

Docker caches layers. If you rebuild after changing only your code (Layer 3), it reuses the cached Python/pip layers, making rebuilds fast.

### Running a Container

`docker run -p 8000:8000 image_name` means:
- `-p 8000:8000` = port mapping: container port 8000 → host port 8000
- `image_name` = which image to run

The container starts, runs the CMD, and your app is live.

### WSL2 (Windows Subsystem for Linux)

On Windows, Docker Desktop needs WSL2—a lightweight Linux environment running inside Windows.

Docker runs in that Linux VM, which is why:
- Docker containers run Linux
- Docker Desktop shows "docker-linux" context
- Kernel is Linux-based even on Windows

## Environment Blocker Resolved

**Issue:** Docker Desktop failed with "Virtualization support not detected"

**Root cause:** WSL2 was not installed, so Docker's Linux backend couldn't start.

**Solution:** Install WSL2 from Windows features. This enables:
- Hyper-V virtualization
- Linux kernel inside Windows
- Docker daemon to run

**Lesson:** Platform requirements are part of the setup. Understanding why each requirement exists (not just installing blindly) is critical.

## Files Changed

```
data-platform-engineering/
├── Dockerfile               (new, Docker recipe)
├── app/
│   ├── main.py
│   ├── __init__.py
├── requirements.txt
├── test_health.py
└── README.md               (checkpoint marked complete)
```

## Verification Performed

1. ✅ Installed Docker Desktop
2. ✅ Enabled WSL2 (resolved virtualization blocker)
3. ✅ Verified Docker engine: `docker --version` and `docker info`
4. ✅ Built the image: `docker build -t data-platform-api:v1 .`
   - Pulled python:3.11-slim base image
   - Copied files, installed dependencies
   - Image built successfully
5. ✅ Ran the container: `docker run -p 8000:8000 data-platform-api:v1`
6. ✅ Tested live endpoint: `curl http://localhost:8000/health`
   - Response: `{"status":"healthy"}` (200 OK)

## Key Architecture Insight

The platform now has a **reproducible, isolated service**:
- The image encapsulates the entire app + runtime
- Same image works on laptop, CI/CD, production
- Foundation for Docker Compose (run multiple services together)
- Foundation for Kubernetes (orchestrate many containers)

## Next Checkpoint (004)

Add **Docker Compose** to run PostgreSQL + FastAPI together locally.

**Why:** We've containerized one service. Now we need multiple services (API, database, object storage) running in harmony. Docker Compose orchestrates that.

**Prep reading (20–30 minutes):**
1. docker-compose.yml syntax: `services`, `ports`, `volumes`, `environment`
2. Service networking in Compose
3. Health checks in Compose

Do not study Kubernetes yet. Compose is the next step.

## Key Takeaways

- A Dockerfile is a recipe; `docker build` creates a snapshot
- Images run as containers; containers are ephemeral instances
- Docker solves the "works on my machine" problem
- WSL2 is the foundation for Docker on Windows
- Containerization is a prerequisite for orchestration

