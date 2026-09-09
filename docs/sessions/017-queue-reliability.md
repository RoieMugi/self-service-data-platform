# Session 017 - Queue Reliability

**Date:** 2026-09-09 (Asia/Jerusalem)

**Status:** Complete for the agreed basic reliability scope. Mid-processing
interruption/recovery and final Grafana visual verification were explicitly deferred.

## Objective and learning workflow

Handle terminal duplicate deliveries and recorded processing failures without
stopping the worker unnecessarily; verify basic worker downtime behavior.
The user edited application code step by step. The assistant edited tests under
explicit authorization, then documentation and cosmetic cleanup at session close.

## Work completed, step by step

1. Reviewed both READMEs, study notes, timeline, recent session records, repository
   memory skills, and relevant application/tests. Agreed three tasks: duplicate
   handling, failure/restart behavior, and verification/documentation.
2. Explained how processing can complete before RabbitMQ receives acknowledgment.
   Kept the atomic queued-to-running claim as the authority to start execution.
3. After a refused claim, added a run lookup and normal return for succeeded runs.
   This lets the worker acknowledge duplicates without processing or metric changes.
4. Added six test cases and adapted the existing claim-failure test. The user
   reported 82 passing tests.
5. Extended the terminal-state check to failed runs. Corrected return indentation
   together so missing/nonterminal runs still raise. Updated test parameterization;
   the user again reported 82 passing tests.
6. Added a ProcessingError handler in the worker. It rereads the run and acknowledges
   only a confirmed succeeded/failed state, returning to avoid a second acknowledgment.
   Lookup failures, missing/nonterminal states, and unexpected exceptions still stop
   consumption without acknowledgment. Acknowledging failure does not make it success.
7. Expanded tests for terminal outcomes across error categories, unresolved states,
   lookup failure, and consumer continuation to another job. The user reported
   96 passing tests from `python -m pytest -q`; timings/warnings were not supplied.
8. The user rebuilt/restarted API and worker and confirmed dependencies healthy.
9. Created a header-only CSV through the user's terminal and uploaded it successfully.
   Corrected use of a dataset ID in the process endpoint to the returned upload ID.
   Submission returned 202; GET showed the run failed. RabbitMQ showed 0 ready,
   0 unacknowledged, 1 consumer.
10. Submitted a known valid upload without restarting the worker. The new run
    succeeded with three rows, passed validation, and no error.
11. Republished the succeeded run ID directly using the existing publisher. An initial
    Python -c command failed because of PowerShell quoting and published nothing.
    A single-quoted here-string piped to `docker compose exec -T api python -`
    succeeded. The queue emptied with one consumer and run timestamps stayed unchanged.
12. Stopped the worker and submitted valid work. GET showed queued with null start,
    completion, and result fields; RabbitMQ showed 1 ready, 0 unacknowledged, 0 consumers.
    Starting the worker completed that same run with three rows; queue returned to 0/0/1.
13. Explained the remaining crash-after-claim gap and proposed a controlled exercise
    with explicit manual recovery. The user stopped the worker, then cancelled further
    exercises in favor of closing the session. No helper, simulated crash, or recovery
    mutation was performed. Requested `docker compose start worker`; completion of
    that final restart was not confirmed.
14. At authorized close, updated both READMEs and timeline, created this record, and
    aligned logger argument indentation in main.py without changing control flow.
    Tests cannot run in the assistant terminal: the virtual environment points to an
    unavailable Python311 installation. The 96-pass report predates cosmetic cleanup.

## Live evidence

Valid upload: `d64523df-8a01-4f21-a9a0-51fc872d45fb`.
Header-only upload: `0f3d5904-ecb8-4639-a9b0-414d0a7b129d`.

| Scenario | Run ID | Observed result |
|----------|--------|-----------------|
| Header-only CSV | d63c8f23-abd0-4fb8-bc79-5c258f56f581 | Failed; queue 0 ready / 0 unacknowledged / 1 consumer |
| Valid work after failure; then duplicate | 964b15fb-cd60-4587-833a-2e73243eb2dd | Succeeded, 3 rows, validation passed, no error; duplicate left timestamps unchanged |
| Queued during worker downtime | 1f8d8499-df77-42a8-b8aa-1f8917a688ab | Queued with no start; then succeeded, 3 rows, queue 0/0/1 |

Duplicate-test run start: `2026-09-09T00:56:29.455567Z`.
Duplicate-test run completion: `2026-09-09T00:56:30.433003Z`.
All live evidence and test outcomes were supplied by the user.

## Files changed

- `app/main.py`: terminal duplicate lookup/skip and cosmetic logger indentation.
- `app/worker.py`: confirmed-terminal handling after ProcessingError.
- `test_messaging.py`, `test_health.py`: reliability tests and lookup mocks.
- `csv_test_files/session17-empty.csv`: header-only live validation fixture.
- `README.md`, `docs/sessions/README.md`, `docs/sessions/TIMELINE.md`, this record.

Sessions 014-016 changes were already uncommitted when this session started.
The authorized Git close includes that required foundation together with Session 017;
it must not be described as new Session 017 implementation. No migration was applied
today. Migration 003 must not be reapplied to the previously upgraded local database.

## Limitations and deferred work

- A crash after claiming can leave running state indefinitely; redelivery then stops
  the worker. No lease, automatic restart/retry, or stuck-run recovery tool exists.
- Manual recovery was discussed only; neither implemented nor verified.
- Queued-worker downtime was verified, not mid-processing crash or broker restart durability.
- Database insertion and broker publication remain non-atomic; no outbox/reconciliation.
- Malformed messages are discarded without a dead-letter queue.
- Long-job heartbeat behavior, concurrent workers, and final Grafana visuals remain unverified.
- Worker startup logging and diagnostics for errors raised inside the ProcessingError
  handler still warrant review; sibling except blocks do not catch those raised errors.
- Reprocessing an upload uses the same curated output key; no per-run output versioning.
- Existing orphan cAdvisor container was not removed. No infrastructure/data cleanup performed.

## Next checkpoint and estimate

Confirm the worker is running after the cancelled exercise. Begin Session 018 by
choosing cloud/provider and deployment details together, then introduce Terraform,
networking, IAM, and secrets through the platform deployment. The remaining estimate
is 2-4 sessions after 017, targeting Phase 1 completion in 019-021. This is a reproducible
learning deployment milestone with the recovery limitations above, not production hardening.
