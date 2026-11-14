# R06–R10 implementation checkpoint

**Date:** 2026-11-14
**Status:** Code and focused tests added; clean-stack and live fault-injection acceptance pending.

## Changes

| Session | Failure addressed | Implemented boundary |
|---|---|---|
| R06 | A dead worker leaves `running` indefinitely. | Five-minute leases, heartbeats, three-attempt limit, expired-run reconciliation, token-guarded finalization, and separate Parquet keys per attempt. Historical running rows without leases require operator review. |
| R07 | A queued database row can lose its broker publication. | The run and outbox intent commit together. The reconciler retries pending intents with broker confirms; duplicate deliveries use the run claim, and recoverable running duplicates may be acknowledged. |
| R08 | Concurrent DuckDB children can multiply resource use. | A process-local semaphore (`QUERY_CONCURRENCY_LIMIT`, default 2) guards query, CSV export, and table-save endpoints from metadata lookup through storage transfer and execution. Excess requests receive HTTP 429. This is not a multi-instance or OS memory guarantee. |
| R09 | Ambiguous database commit can make raw-object cleanup delete a referenced file. | The API preserves the object and returns the stable upload ID. `GET /uploads/{upload_id}` can check the outcome. `scripts/audit_objects.py` reports referenced-missing and unreferenced-stored keys without deleting anything. |
| R10 | A save retry can create another table. | An optional UUID `Idempotency-Key` identifies a logical save. A repeat returns the existing table if source, name, description, and SQL match. Different input returns HTTP 409; uncertain commits are looked up by operation ID. |

## Verification and deployment limits

The owner’s baseline suite passed 202 tests before this increment. Focused API, worker, and failure-boundary tests passed **108 tests**; the new reliability file separately passed **11 tests** after the idempotency-header case was added. Three query-process tests that previously timed out passed together in a focused run. The latest full suite reported **212 passed, 2 failed, 1 warning** in 193.56 seconds. Both failures were existing query-executor tests whose child processes exceeded the 10-second deadline on this loaded local host. There is no passing full-suite result for the final code. No live fault injection, fresh Compose smoke run, or CI integration result has been recorded. Do not claim R06–R10 acceptance from mock tests alone.

Migration 005 was applied to the owner's retained local PostgreSQL database on 2026-11-14. A direct read verified all four new columns and the `processing_outbox` table. Other existing databases still need the migration before rebuilding services; fresh databases use `db/init.sql`. Do not delete retained volumes to get a clean test; use a disposable project or the isolated CI job. The new `reconciler` service is needed for publication and lease recovery.

**Live update (2026-11-14):** The owner rebuilt API, worker, and reconciler against the migrated retained database. The worker restarted twice during RabbitMQ startup, then stabilized. A live `scripts/verify_saved_tables.py` run passed: dataset `511feae7-7bf7-4883-b7e6-9b9bea202c20`, run `480ab46d-46a2-4894-a0a0-8c70b69e0bec`, saved table `e5fe355d-0c6d-4e38-9dde-b20b765bbfd7`, and derived table `2b2f8b68-e652-4328-9069-1c6a2bdd9752`. This proves the normal upload, processing, query, save, CSV export, and download path on the retained stack. It does not replace clean-stack or fault-injection evidence.

Read-only object inventory from the running API image:

```powershell
docker compose exec api python scripts/audit_objects.py
```

The report can contain orphaned objects left by uncertain operations; inspect it before any cleanup. This increment performs no automatic deletion.

The short [architecture decision notes](DECISIONS.md) record why PostgreSQL, MinIO, RabbitMQ, and DuckDB remain in this local design.
