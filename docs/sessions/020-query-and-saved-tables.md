# Session 020 - Dataset queries and saved tables

**Dates:** 2026-09-11 through 2026-09-14 (Asia/Jerusalem)

**Status:** Complete, including the user-executed proof of concept.

## Objective and workflow

Add bounded SQL previews and persist query results as new reusable tables. The
user selected assistant implementation, explained one increment at a time, and
then authorized execution of the remaining Session 020 feature work. Downloads
remain Sessions 021-022; deployment wrap-up follows in 023-024 if needed.

## Implementation

- app/main.py: request/response contracts, bounded MinIO download, run-query route,
  table catalog read/list, save-from-run, query-saved-table, and derive-from-table.
- app/query_executor.py: separate child process, restricted SELECT execution,
  preview limits, full bounded Parquet export, and preserved empty-result schema.
- db/init.sql and migration 004: saved_tables metadata with unique names/objects,
  exactly one source reference, original SQL, row count and file size constraints.
- Terraform/api-lab/main.tf: new executor source hash participates in rebuild plans.
- test_query_api.py, test_query_executor.py, test_saved_tables.py: behavior tests.
- scripts/verify_saved_tables.py: repeatable live smoke test that retains samples.
- README.md and docs/query-tables.md: current scope, endpoints and limitations.

## Verification and environment

- Earlier Python-not-found failures were sandbox access failures. Running the
  existing .venv interpreter outside the sandbox succeeded; no reinstall occurred.
- Existing preview suite: 27 passed. Final `python -m pytest -q`: **140 passed,
  1 warning in 15.47s**. Warning concerns python_multipart's deprecated import path.
- Started existing Compose PostgreSQL, MinIO and RabbitMQ; applied migration 004
  successfully (BEGIN / CREATE TABLE / COMMIT). There were 17 existing runs.
- Rebuilt and started Compose API and worker. The live smoke test added one run
  and two tables: 18 runs afterward; no existing dataset/run was deleted.
- Verified upload/process, preview truncation, full save, listing/lookup, re-query,
  duplicate-name rejection, rejected DROP, and a second derived table totaling 35.
- Restarted API and queried persisted regional totals again: north 30, south 5.
- PostgreSQL confirmed source-run lineage for the regional table and source-table
  lineage for the grand-total table. IDs are recorded in docs/query-tables.md.
- One permission-review timeout delayed migration; a read check confirmed it had
  not run, and the allowed retry succeeded. No approval blocker remains.

## Guided proof of concept

The user switched to executing each step while the assistant explained its code:

1. Created csv_test_files/session20-customer-sales.csv with Alice 150, Bob 120,
   Charlie 180 and Dana 200 (synthetic data).
2. Registered dataset d5622fdc-5423-4834-adc7-3ec1dc51748b (HTTP 201).
3. Uploaded the 86-byte CSV as upload 246cbcbf-1fde-4acc-99dd-e6cb2b6e6c29 (201).
4. Submitted processing run 3167cc91-5af4-4279-90ec-15dd04f8cd4a (202 queued),
   then verified succeeded, four rows and validation passed through the GET route.
5. Queried all four rows. Corrected a 404 caused by using a run UUID on the saved-table
   route; distinguished /processing-runs/{run_id} from /tables/{table_id}.
6. Aggregated the new sample: count 4, total 650, average 162.5, maximum 200.
7. Queried the previous Session 13 artifact independently: run
   964b15fb-cd60-4587-833a-2e73243eb2dd, count 3, total 415.75, average 138.58,
   maximum 210.25. Compared the summaries; no cross-file SQL join was performed.
8. Saved session20_customer_sales_summary, table aa20d66f-aa0e-4784-bbe0-7b6e5334e0d2:
   one row, 658-byte Parquet, linked to the new source run.
9. Queried that saved table in a new request and verified the same summary.
10. Continued into the saved-table download exercise recorded in Session 021.

The guided demo added its own upload/run/table after the earlier assistant smoke
test. The difference in sample totals is 234.25; these are synthetic examples,
not evidence of a real time-series business trend.

## Limits and retained state

Compose API, worker, database, MinIO and RabbitMQ remain running. Existing cAdvisor
was untouched. Terraform/Kubernetes lab resources and images were not updated.
No commit, push, or PR was created.

The query executor remains a local learning component, not a complete public SQL
sandbox. Save has a 100,000-row / 20 MiB acceptance limit; preview is limited to
1,000 rows / 1 MiB JSON. The 10-second child deadline excludes storage/database
access. No aggregate concurrency or OS memory quota is implemented.

Storage/metadata writes are not atomic. Confirmed duplicate insert failures clean
up the new object; uncertain commits preserve it and return its ID for inspection.
Other failures may leave orphan objects; automated reconciliation is deferred.
Table names are catalog labels; each selected source is queried as dataset.
General query history, table mutation, cross-dataset joins, GUI and LAN verification
remain outside this increment. Interrupted-processing recovery and Grafana visual
verification remain deferred.

## Next step

Sessions 021 and 022 subsequently completed downloads and CSV export. Separate
records preserve each session. Phase 1 still has local deployment wrap-up.
