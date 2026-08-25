# Session 001 - Project Foundation

**Date:** 2026-08-10  
**Status:** Complete

## Objective

Turn the broad learning roadmap into one achievable MVP and establish a durable
record of our work.

## What we decided

We will build a self-service batch data platform as a sequence of small,
verifiable checkpoints.

The MVP flow is:

```text
Register CSV -> trigger run -> store raw data -> validate -> transform
             -> write Parquet -> expose run status
```

The initial stack is FastAPI, PostgreSQL, MinIO, DuckDB, Python, and Docker
Compose.

We deliberately deferred Kubernetes, Terraform, Kafka, Spark, authentication,
a frontend, and AI features. They will be introduced only when the working MVP
gives us a concrete reason to use them.

## Concepts learned

- A platform exposes a reusable, self-service contract to its users.
- A vertical slice proves the whole user outcome with minimal infrastructure.
- Docker Compose is appropriate for the first local multi-service environment.
- Session records make technical decisions and learning progress reproducible.

## Files changed

- Added `README.md` with the MVP, architecture, and checkpoints.
- Added `docs/sessions/README.md` describing the logging convention.
- Added this session record.

## Verification

- Confirmed that the workspace initially contained only
  `Platform_Engineering_Study_Notes.md`.
- Git could not be invoked because it is not installed or not available on the
  current `PATH`.

## Reading before the next checkpoint

Spend about 20-30 minutes reviewing:

1. The difference between an HTTP route and an application health endpoint.
2. FastAPI path operations and response models.
3. Why dependency files pin or constrain package versions.

Do not study Kubernetes or Terraform yet. They are not needed for the next
engineering decision.

## Next checkpoint

Create the smallest FastAPI service with:

- `GET /health`;
- a small automated test;
- local run instructions.

