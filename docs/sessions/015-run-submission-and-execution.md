# Session 015 - Run Submission and Execution

**Date:** 2026-09-08

**Status:** Complete for run separation and verification; queue/worker deployment remains pending.

## Objective

Make queued runs readable and separate submission from execution so a future
worker can process an existing run ID. Preserve the synchronous API behavior.

## Work completed, step by step

1. Reviewed both repository README files, study notes, timeline, Session 014,
   relevant source/schema files, and the two saved repository memory skills.
2. Agreed a practical remaining Phase 1 roadmap of 5-7 sessions including 015,
   replacing the padded 12-18-session estimate. Saved it in the root README.
   Related cloud topics will be learned together through one deployment.
3. Added `created_at` to `ProcessingRunResponse` and the run SELECT query;
   allowed `started_at` to be null so queued records can be read through the API.
4. Updated response fixtures and added a queued-run response test. The user
   reported `44 passed`.
5. Changed `create_processing_run()` to insert a queued record. Explained that
   PostgreSQL supplies `created_at` through its default; omitting `started_at`
   leaves it null until execution begins. No schema migration was needed.
6. Added `claim_processing_run(run_id)`: a single UPDATE changes queued to
   running and sets `started_at`, returning a record only when the claim succeeds.
7. Connected claiming before processing. A failed or unavailable claim stops
   execution without downloading data or marking an unclaimed run as failed.
8. Split `submit_processing(upload_id, correlation_id)` from
   `execute_processing(run_id, correlation_id)`. Submission validates the upload,
   creates the run, and calls execution immediately. Execution claims the same
   ID and resolves its upload independently. The HTTP wrapper translates errors.
9. Added failure recording, lifecycle logging, and metrics for upload lookup
   failures after claiming. Worked through Python indentation and fixed the
   function boundary and lookup block with the user's authorization.
10. Updated processing tests with claim mocks and queued creation fixtures.
    Added seven cases for claim results, claim failures, post-claim lookup
    failures, and execution without creating a second run. The user reported
    `51 passed`.
11. The user rebuilt the API, processed a known upload, read the stored run,
    and confirmed a completed run could not be claimed again.
12. Updated both README files and the timeline, created this record, aligned
    the queued INSERT SQL, clarified the submission docstring, and added spacing
    before the submission-to-execution return. End cleanup changes presentation
    only; the test suite was not rerun after that cleanup.

## Concepts and decisions

- Submission time and execution start time describe different events.
- INSERT values are supplied by the caller; defaults fill omitted columns;
  RETURNING retrieves the resulting database values.
- A conditional UPDATE checks and changes the queued state in one operation.
- A missing claim result does not establish whether the run is missing,
  already running, or complete. Do not overwrite its state on that basis.
- Execution receives a run ID and correlation ID, independently of HTTP.
- The same run ID is retained from submission through completion.
- HTTP processing still waits for completion and returns 200 on success.
- The Phase 1 finish line is a reproducible learning deployment, with access
  controls and persistent data. Advanced production hardening remains later work.

## Files changed in Session 015

- `app/main.py`
- `test_health.py`
- `README.md`
- `docs/sessions/README.md`
- `docs/sessions/TIMELINE.md`
- `docs/sessions/015-run-submission-and-execution.md`

Schema changes and migration 003 in the working tree belong to Session 014.

## Verification

The user executed tests and Docker/API checks and shared the results:

- `python -m pytest -q`: first `44 passed`, then `51 passed` after run separation.
  Timing and warning details were not supplied for those runs.
- `docker compose up -d --build api`: user confirmed the API was up.
- POST processing for upload `d64523df-8a01-4f21-a9a0-51fc872d45fb` returned
  run `d54c2faa-43e2-4d06-9a30-c13b4f4d7b01`, status `succeeded`, row count 3,
  Parquet format, and validation `passed`.
- GET of that run returned the same ID and results, with no error message:

  | Field | UTC timestamp |
  |-------|---------------|
  | created_at | 2026-09-08T00:33:38.715142Z |
  | started_at | 2026-09-08T00:33:38.751561Z |
  | completed_at | 2026-09-08T00:33:39.074104Z |

- The submission-to-start interval was approximately 36 ms; start-to-completion
  was approximately 323 ms.
- Calling `claim_processing_run()` inside the API container for that completed
  run returned `None`, confirming that the real database rejected that claim.
- The assistant could not execute pytest: Python was unavailable through PATH,
  the local virtual environment could not locate its configured interpreter,
  and `py -0p` reported no installed Pythons. Passing results above are user-reported.

## Limitations and follow-up

- No RabbitMQ, separate worker, HTTP 202 contract, or queue handoff exists yet.
- Mocked claim tests and the live completed-run rejection do not constitute a
  concurrent-worker test or crash-recovery verification.
- Claim exceptions currently become internal processing errors; claim failures
  do not yet emit the same lifecycle metrics as post-claim processing failures.
- Reliable database-to-broker handoff, duplicate delivery, acknowledgments,
  stuck-run recovery, correlation propagation, and worker metrics need design
  during queue integration and the following reliability session.
- Curated output still uses an upload-based object key, so reprocessing writes
  the same location. Per-run output versioning remains unimplemented.
- Session 014's Grafana query observations and orphan cAdvisor container were
  outside this session's scope and remain unverified/unresolved here.
- No commit, push, or new CI result is claimed. Existing Session 014 changes
  remain in the working tree alongside this session's changes.

## Next small step

Session 016: explain and agree the API-to-RabbitMQ-to-worker flow and message
contract, then add it in small increments. Follow the root README roadmap and
the user's learning-together rule: explain each task and wait; implementation
requires the user's instruction.
