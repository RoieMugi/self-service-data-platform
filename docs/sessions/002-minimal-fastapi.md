# Session 002 - Minimal FastAPI Service with Health Endpoint

**Date:** 2026-08-19  
**Status:** Complete

## Objective

Establish a working FastAPI application with a health check endpoint (`GET /health`)
that can be tested locally. This is the first vertical slice of the platform—proving
that the framework works and setting a pattern for all future endpoints.

## What we built

A minimal FastAPI service with:

- One HTTP route: `GET /health`
- Response: `{"status": "healthy"}` with HTTP 200 (OK)
- Automated tests using pytest
- Local development server using uvicorn

## Architecture & Concepts Learned

### HTTP Routes vs. Health Endpoints

A **route** is a path your web server responds to (e.g., `/health`).

A **health endpoint** is a specific route that a monitoring system can call to ask:
"Is the service running?" Without it, external systems (load balancers, orchestrators,
monitoring tools) cannot know if your service is alive.

### FastAPI Path Operations

FastAPI uses Python decorators to define routes:

```python
@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

The decorator `@app.get("/health")` registers an HTTP GET request handler at the path
`/health`. The function below it runs when a request arrives. Returning a dict
automatically serializes it to JSON.

### Dependency Pinning in requirements.txt

Pinning exact versions ensures reproducibility:

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pytest==7.4.3
httpx==0.25.2
```

Any machine running `pip install -r requirements.txt` gets the exact same packages.
This prevents "works on my machine" problems and makes CI/CD reliable.

### TestClient

FastAPI provides `TestClient`, which simulates HTTP requests without running a server:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
response = client.get("/health")
assert response.status_code == 200
```

This allows fast, isolated tests during development.

### uvicorn: The Application Server

`uvicorn` is an ASGI (Asynchronous Server Gateway Interface) web server. It:

- Runs your FastAPI app
- Listens for HTTP requests on a port (default: 8000)
- Routes requests to your route handlers
- Returns responses to clients

The `--reload` flag restarts the server when you edit files (convenience for development).

## Decisions & Tradeoffs

1. **One endpoint only:** We resisted the urge to add more features. Keeping it minimal
   proves the infrastructure works and avoids scope creep.

2. **Local-only development:** We run the server on localhost, not Docker yet. This keeps
   setup simple for the first checkpoint. Docker comes in Checkpoint 003.

3. **Manual testing + automated tests:** We verified the endpoint both with automated
   pytest tests and with a live curl request. Both approaches are valuable:
   - Automated tests catch regressions automatically.
   - Live testing confirms real HTTP behavior.

## Files Changed

```
data-platform-engineering/
├── app/
│   ├── __init__.py              (new, empty package marker)
│   └── main.py                  (new, FastAPI app)
├── requirements.txt             (new, dependencies)
└── test_health.py               (new, automated tests)
```

## Verification Performed

1. ✅ Installed dependencies: `pip install -r requirements.txt`
2. ✅ Ran automated tests: `python -m pytest test_health.py -v`
   - Both tests passed: `test_health_returns_200` and `test_health_returns_healthy_json`
3. ✅ Started server: `python -m uvicorn app.main:app --reload`
4. ✅ Made live request: `curl http://localhost:8000/health`
   - Response: `{"status":"healthy"}` with status code 200

## Blockers

None. Setup and implementation were straightforward.

## Next Checkpoint (003)

Containerize the FastAPI service with Docker.

**Why:** We currently run on localhost. The next step is to package the app and all
its dependencies into a Docker image. This:
- Makes deployment consistent across environments
- Prepares us for Docker Compose (Checkpoint 004)
- Proves the service can run in isolation

**Prep reading (20–30 minutes):**

1. Dockerfile syntax: `FROM`, `COPY`, `RUN`, `CMD`
2. Docker image layers and caching
3. Multistage builds (optional for this phase)

Do not study Kubernetes or container orchestration yet. Docker alone is the goal.

## Key Takeaways

- A platform starts with one working endpoint.
- Tests + live verification ensure reliability.
- Dependency pinning prevents environment surprises.
- Small, focused increments make progress visible and mistakes easy to fix.

