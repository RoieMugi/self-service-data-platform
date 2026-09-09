# Session 016 - RabbitMQ and Asynchronous Worker

**Date:** 2026-09-08 to 2026-09-09 (Asia/Jerusalem)

**Status:** Complete for asynchronous integration and worker metrics;
reliability verification remains Session 017 work.

## Objective

Move existing CSV-to-Parquet execution out of the HTTP request into a separate
worker, preserving the run ID, database lifecycle, and correlation context.

## Work completed, step by step

1. Reviewed both README files, study notes, timeline, Sessions 014-015, relevant
   source files, and both repository memory skills. Retried the requested memory
   folder read successfully with expanded read access.
2. Agreed three tasks: define the message and submission contract, integrate
   RabbitMQ and a worker, and verify processing and observability. Continued the
   learning-together workflow, with the user making changes unless explicitly
   delegating edits. Future bulk edits should state their size upfront.
3. Discussed acceptance versus completion and the database-to-broker gap. Chose
   confirmed publishing with explicit submission errors for this increment;
   transactional outbox and recovery were explained but not implemented.
4. Added RabbitMQ to Compose with a named volume, credentials, a health check,
   and a loopback-only management port. Validated Compose, started the broker,
   and verified health and dashboard access. The image is `rabbitmq:4-management`;
   the dashboard displayed version 4.3.5, not an exact image pin.
5. Added API broker configuration and startup dependency, then installed
   `pika==1.3.2`. The user supplied successful pip installation output.
6. Created `app/messaging.py`: connection timeouts, durable queue declaration,
   JSON run/correlation IDs, persistent messages, publisher confirmations,
   mandatory routing, and connection cleanup. Message IDs are identifiers,
   not automatic deduplication.
7. Added `ProcessingSubmissionResponse` and changed submission to publish the
   existing queued run. Changed POST success to HTTP 202 and publication failure
   to HTTP 503 with the run ID. Preserved state on uncertain delivery. At the
   user's request, corrected a misplaced publishing block and indentation in
   `app/main.py`; the user then verified compilation with no output.
8. Created `app/worker.py` incrementally: decoded and validated UUID fields,
   reused `execute_processing()`, acknowledged after success, and rejected
   malformed messages without requeueing. Execution errors propagate and stop
   consumption; connection closure permits redelivery. Explained tuple
   unpacking, callbacks, function imports, and execution in the worker process.
9. Added manual acknowledgment, prefetch 1, and a consuming loop. Deployed a
   worker using the same Dockerfile but `python -m app.worker`, with database,
   storage, and broker settings. No general multi-job dispatcher was added.
10. Verified one RabbitMQ consumer despite empty worker startup logs. Submitted
    the known upload, received HTTP 202, read the same run as succeeded, and
    observed Ready 0, Unacked 0, Consumers 1 afterward.
11. Ran the old suite through the user's terminal: six endpoint processing tests
    failed because they now reached publishing. With explicit bulk-edit
    authorization, adapted those six to direct execution and added 25 cases in
    `test_messaging.py`: 5 submission, 6 publisher, and 14 worker cases, including
    parameterized variations. The suite reached 76 passing tests.
12. Added the worker metrics server on port 8001 and a Prometheus worker scrape
    job. Rebuilt the worker, restarted Prometheus, verified the target UP, then
    verified `platform_processing_runs_total{job="worker",outcome="succeeded"}`
    returned 1 after another successful job.
13. Reviewed dashboard and alert queries. Updated last-success aggregation to
    select the latest positive timestamp, changed duration to recent worker
    histogram rates, and removed the memory data-source UID trailing space.
    Existing processing outcome queries and the infrastructure alert already
    include worker series. Final visual dashboard verification was skipped.
14. Mocked metrics-server startup in worker main-loop tests to avoid binding
    port 8001. The user reported 76 passing tests again.
15. At authorized session close, updated both README files and the timeline,
    created this record, grouped imports, removed the unused worker
    `ProcessingError` import, and normalized spacing/trailing whitespace in
    touched code/configuration. No processing behavior was changed at close.

## Verification evidence

All runtime/test results below were supplied by the user; the assistant's
terminal could not locate a usable Python interpreter or Docker executable.

- Compose validation returned no output; RabbitMQ showed healthy.
- API and worker containers both showed Up; RabbitMQ showed one consumer.
- POST returned 202 and run `44273860-6def-42be-b558-26f5f1dee480`, initially queued.
- GET returned the same run, upload `d64523df-8a01-4f21-a9a0-51fc872d45fb`,
  status succeeded, row count 3, validation passed, and null error message.
- Curated output key:
  `3a3eb662-81e7-478c-b8c7-dde042be590c/d64523df-8a01-4f21-a9a0-51fc872d45fb/data.parquet`.

| Field | UTC timestamp |
|-------|---------------|
| created_at | 2026-09-08T23:39:28.342602Z |
| started_at | 2026-09-08T23:39:29.105212Z |
| completed_at | 2026-09-08T23:39:30.365037Z |

Submission-to-start was about 0.763 seconds; processing was about 1.260 seconds.
RabbitMQ subsequently showed Ready 0, Unacked 0, Consumers 1.

- Initial suite: `6 failed, 45 passed, 1 warning in 8.27s`.
- After test adaptation/additions: `76 passed, 1 warning in 5.57s`.
- After metrics startup was mocked: user reported `76 passed`; timing and
  warning details were not supplied for that final run.
- The earlier warning was Starlette's existing multipart pending deprecation.
- Prometheus screenshot showed `worker:8001` UP; a later screenshot showed
  the worker successful-run counter at 1.
- The suite was not rerun after session-end import/whitespace cleanup.

## Files changed in this session

- `app/main.py`, `app/messaging.py`, `app/worker.py`
- `requirements.txt`, `docker-compose.yml`, `prometheus.yml`
- `grafana/dashboards/data-platform-operations.json`
- `test_health.py`, `test_messaging.py`
- `README.md`, `docs/sessions/README.md`, `docs/sessions/TIMELINE.md`
- `docs/sessions/016-rabbitmq-worker.md`

Existing schema/migration changes and Sessions 014-015 records predate this
session. No migration was applied in Session 016; migration 003 must not be
reapplied to the previously upgraded local database.

## Limitations and follow-up

- Database insert and publication are separate operations. No outbox, automatic
  resubmission, or reconciliation closes the gap. A 503 can mean uncertain
  delivery; retrying the POST can create another run.
- Conditional claiming prevents a second queued-to-running transition, but does
  not provide complete duplicate-delivery or crash recovery. A redelivered
  running/completed/failed run currently cannot be claimed and stops the worker.
- All execution errors stop the worker, even a durably recorded validation
  failure. Distinguish terminal outcomes, transient failures, and stuck runs
  before adding automatic restarts or retries. No live failure/restart or
  concurrent-worker test was performed in this session.
- Malformed messages are discarded without a dead-letter queue. Publisher
  connection cleanup can itself fail after successful publication, yielding
  an uncertain submission result. These need review during reliability work.
- Synchronous processing can occupy the Pika consuming thread; heartbeat and
  long-running-job behavior remain unverified for larger inputs.
- Worker startup INFO logs were not visible. Processing logs carry correlation
  context, but general worker logging configuration still needs review.
- Metrics reset per process restart; PostgreSQL retains history. Last-success
  metrics are unavailable after all relevant processes restart until a new
  success. API resource panels/alert still monitor only the API.
- Final Grafana visual verification was skipped. The existing orphan cAdvisor
  container warning remains unresolved; no container or data was deleted.
- Reprocessing writes the same upload-based Parquet key. No per-run output
  versioning, new commit/push, or new CI run is claimed.

## Next small step and Phase 1 estimate

Session 017: explain how to handle a delivered message whose run is already
running or terminal, then agree and verify duplicate/failure/restart behavior
one small step at a time. Follow the user's instruction to explain and wait
before implementation unless edits are explicitly delegated.

The agreed roadmap leaves **3-5 sessions after Session 016**, targeting Phase 1
completion in Sessions 019-021: reliability in 017, Terraform/cloud in 018,
Kubernetes in 019, and optional deployment/CI/recreation/cleanup in 020-021.
This remains an estimate for a reproducible learning deployment.
