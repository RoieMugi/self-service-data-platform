# R05 - Interrupted-run recovery design

**Date:** 2026-11-14
**Status:** Design draft; failure tests and implementation pending.

## Current failure

`claim_processing_run` changes `queued` to `running` once. A dead worker leaves that row `running`; redelivery cannot claim it. Success/failure updates check only `status = 'running'`, so a late worker could finalize after a future retry. The run-specific object key introduced in R01 does not distinguish attempts.

## Proposed guarantee

Each attempt has a monotonically increasing attempt number, random claim token, lease expiry, and heartbeat timestamp. Claiming a queued run issues attempt 1. A recovery command scans expired running leases and either issues the next attempt or records terminal failure after a configured maximum. Every heartbeat and final database update checks both run ID and claim token. An expired token cannot extend or finalize a run.

Object writes also need fencing. Store each attempt under `dataset_id/upload_id/run_id/attempt_number/data.parquet`. Only the active token may publish that attempt's key into the run row. A stale attempt may leave an unreferenced object, but it cannot overwrite the current attempt's bytes or become the discoverable output. Object cleanup is a separate audited task.

## State and races to test before R06

| Case | Expected outcome |
|---|---|
| Death after claim | Lease expires; recovery schedules a bounded retry. |
| Redelivery before expiry | Existing live attempt remains sole owner. |
| Stale worker resumes after retry | Token check rejects heartbeat/finalization; separate attempt key prevents overwrite. |
| Death after object upload | Retry uses a different object key; old object remains unreferenced. |
| Maximum attempts reached | Run becomes failed with a clear recovery reason. |
| Validation failure | Terminal failure remains terminal; it is not retried as a crash. |

Migration for existing databases must add nullable lease/token fields, an attempt counter with a safe default, and indexes for expired-running lookup. Existing `running` rows need an explicit operator-reviewed migration policy; they must not be silently reclaimed. The recovery trigger should be a bounded worker loop or separate command with one atomic conditional database claim. R06 implements and fault-tests this design.
