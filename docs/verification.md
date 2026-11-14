# Verification map

Use the [README quick start](../README.md#run-locally) to start the local stack. The commands below separate fast source-level checks from live integration checks.

| Claim | Check | Expected result |
| --- | --- | --- |
| API and query behavior | `python -m pytest -q` | All tests pass. |
| Upload through derived table | `python scripts/verify_saved_tables.py` | JSON with `"status": "passed"`; regional totals 30 and 5, grand total 35. |
| Missing and orphaned objects | `docker compose exec api python scripts/audit_objects.py` | JSON lists for raw and curated references; an empty list means no discrepancy at the time of the scan. |
| Recovery and failure boundaries | GitHub Actions integration job | Disposable-stack smoke test, worker and broker recovery, query admission, object inventory, and save retries pass. |

[GitHub Actions run 43638419520](https://github.com/RoieMugi/self-service-data-platform/actions/runs/43638419520) passed 214 pytest tests and the three integration scripts on a fresh disposable stack. The workflow is defined in [.github/workflows/tests.yml](../.github/workflows/tests.yml); it runs on pushes and pull requests to `main`. The integration job starts its own Compose stack, then removes its volumes. The normal smoke test run against your local stack retains its sample dataset, run, and two saved tables.

## What the failure checks cover

The recovery script expires a worker lease, kills a worker after an artifact upload, checks that a stale claim cannot finalize, reaches the retry limit, interrupts RabbitMQ publication, and verifies duplicate delivery behavior. The boundary script fills the process-local query slots, tests an uncertain upload commit, compares stored objects with database references, and retries a saved-table creation after an uncertain commit. These checks deliberately inject faults and should be run only on a disposable stack; CI runs them there.

## Object inventory

`scripts/audit_objects.py` is read-only. It compares PostgreSQL object keys with the raw and curated buckets and reports `referenced_missing` and `unreferenced_stored` lists. A discrepancy needs investigation; the script does not delete or repair objects. Empty lists prove consistency only for the observed point in time.

## Limits of the evidence

The disposable CI stack does not test migration of an existing MinIO data volume to the pinned Silo image. Historical `running` rows without leases require operator review. The project has no authentication, cross-process query admission, backup and restore procedure, or production-scale load claim. A slow local machine may hit the 10-second query deadline even when the same tests pass in CI; inspect the error and system load before attributing that result to a code defect.
