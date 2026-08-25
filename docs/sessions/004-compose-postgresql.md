# Session 004 - Docker Compose and PostgreSQL

**Date:** 2026-08-24  
**Status:** Complete

## Objective

Run the FastAPI service and PostgreSQL together with Docker Compose, verify
database connectivity, and add automated health-endpoint tests.

## What we built

- PostgreSQL 15 service managed by Docker Compose.
- Persistent PostgreSQL named volume.
- PostgreSQL readiness health check using `pg_isready`.
- API startup dependency on database readiness.
- `DATABASE_URL` configuration through the Compose environment.
- `GET /db-health` endpoint for database connectivity.
- Safe database failure responses with detailed server-side logging.
- Automated tests for API health and database-health behavior.

## Concepts learned

- Compose service names provide internal DNS between containers.
- `localhost` inside a container refers to that container, not another service.
- Container startup and service readiness are different states.
- Application health and dependency health should be checked separately.
- Named volumes preserve database data when containers are replaced.
- Unit tests can mock external dependencies.
- Docker and local Python are separate execution environments.
- A project virtual environment isolates local dependencies.
- `.gitignore` and `.dockerignore` solve different problems.

## Verification

- `docker compose config` validated the Compose configuration.
- `docker compose up --build` successfully built and started both services.
- `GET /health` returned HTTP 200.
- `GET /db-health` returned HTTP 200 while PostgreSQL was available.
- After stopping PostgreSQL, `/health` remained available and `/db-health`
  returned HTTP 500.
- Restarting PostgreSQL restored `/db-health` without restarting the API.
- `python -m pytest test_health.py -v` completed with 3 passing tests.
- Final `docker compose ps` showed PostgreSQL healthy and the API running.

## Environment work

- Installed Python 3.11 to match the Docker runtime.
- Created a project-specific `.venv`.
- Installed and initialized Git.
- Added `.gitignore` and `.dockerignore`.
- Removed the obsolete Compose `version` attribute.
- Removed the duplicate `app/Dockerfile`.

## Files changed

- `app/main.py`
- `docker-compose.yml`
- `requirements.txt`
- `test_health.py`
- `.gitignore`
- `.dockerignore`
- `docs/sessions/004-compose-postgresql.md`

## Next checkpoint

Add dataset registration and persist dataset metadata in PostgreSQL.
