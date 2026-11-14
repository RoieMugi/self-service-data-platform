# Query previews and saved tables

Session 020 implementation verified on 2026-09-14. Open http://localhost:8000/docs
against the updated Docker Compose API. The Kubernetes API lab is not configured
with the full storage/worker dependencies and was not updated in this session.

## Endpoints

| Method/path | Purpose |
|-------------|---------|
| POST /processing-runs/{run_id}/query | Preview a succeeded run's output. |
| POST /processing-runs/{run_id}/tables | Save a SELECT result as a named table. |
| GET /tables?limit=50&offset=0 | List saved tables, newest first; limit 1-100. |
| GET /tables/{table_id} | Retrieve table metadata and source information. |
| POST /tables/{table_id}/query | Query a saved table. |
| POST /tables/{table_id}/tables | Save a result derived from a saved table. |
| GET /tables/{table_id}/download | Download the saved table's Parquet file. |
| GET /uploads/{upload_id}/download | Download the original uploaded CSV. |
| GET /processing-runs/{run_id}/download | Download a succeeded run's Parquet output. |
| POST /processing-runs/{run_id}/query/csv | Export a SELECT over a successful run as CSV. |
| POST /tables/{table_id}/query/csv | Export a SELECT over a saved table as CSV. |

Saved-table creation accepts an optional `Idempotency-Key` header containing a UUID. Reuse the same key and request body after a timeout to retrieve the same table; using that key for different input returns HTTP 409. The existing name-conflict rule still applies when no key is supplied.

Stored-file downloads were verified on 2026-09-14. They return attachments without
rerunning SQL or processing. Original CSV downloads preserve bytes and use an
encoded original filename with an ASCII UUID fallback. Limits are 10 MiB for raw
CSV and 20 MiB for Parquet; files are buffered in memory. Lookup failures and
unavailable storage return controlled errors, and storage connections are released
on success and failure. CSV export of query results was completed in Session 022.

## CSV query-result export

Use either /query/csv route with a body such as:

```json
{"sql": "SELECT customer_id, name, amount FROM dataset ORDER BY customer_id"}
```

The response is a UTF-8 CSV attachment with headers and X-Row-Count. In /docs,
execute the request and use Download file. The input only accepts SQL; max_rows
is rejected so a preview limit cannot silently truncate an export. A SQL LIMIT
explicitly included by the caller still applies. Empty results include headers.

The executor materializes the bounded full result and uses DuckDB's
[CSV writer](https://duckdb.org/docs/stable/clients/python/relational_api) for
commas, quotes, multiline fields and Unicode. NULL is written as an empty field;
generic CSV readers may not distinguish NULL from an empty string. CSV does not
carry the Parquet type schema. Values are exported unchanged, not converted into
spreadsheet-specific display text.

Limits: one SELECT, 10,000 SQL characters, 20 MiB input, 100,000 output rows,
20 MiB CSV output, and the existing 10-second child deadline/engine memory settings.
Exceeding an output limit returns 422, never a partial successful CSV. Size is
checked after writing; this remains a bounded local feature, not large-file
streaming or a hard OS resource quota. CSV bytes are buffered for the HTTP response.

Export re-executes SQL against the chosen artifact but creates no saved table,
processing run, or persistent MinIO object. It permits only the application-generated
CSV path for writing, uses the same SELECT/access restrictions as preview/save,
and cleans up temporary files afterward. Missing sources, storage failures and
executor errors use the same controlled status handling as the query endpoints.

Every query references its selected source as `dataset`. Names are catalog labels,
not automatically available SQL identifiers. Choose a table ID through the catalog;
cross-table joins and inserts/updates/deletes are not implemented.

Preview body:

```json
{"sql": "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region", "max_rows": 100}
```

Save body (a separate action that re-executes SQL):

```json
{"name": "sales_by_region", "description": "Regional totals", "sql": "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region"}
```

The 201 response includes the new table UUID, name, original SQL, row count, size,
creation time and exactly one source ID. Parquet lives in the curated bucket at
`tables/{table_id}/data.parquet`; PostgreSQL `saved_tables` stores metadata. Sources
are retained unchanged. Empty results retain their schema and can be saved.
Table names are unique within the saved-table catalog, using case-sensitive
PostgreSQL text equality. This catalog is separate from uploaded `datasets`.

## Limits and error handling

- One parsed SELECT, SQL at most 10,000 characters, one source artifact per request.
- Preview: 100 rows by default, maximum 1,000; `row_count` counts returned rows and
  `truncated` indicates more rows. Dates/decimals and other non-JSON scalar values
  use string representations. Non-finite float serialization fails.
- Save: complete result up to 100,000 rows and 20 MiB Parquet; rejects overflow
  rather than silently saving a truncated preview. SQL LIMIT still applies.
- Each input is capped at 20 MiB. The child has a 10-second deadline, one DuckDB
  thread, 256 MB engine memory budget, and no disk spill. The engine memory budget
  is not a process memory cap; no application-wide concurrency limit exists.
- External access is disabled after loading. Save mode permits only the generated
  output path for the application writer, following DuckDB's
  [file access controls](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview).
- Preview JSON is capped at 1 MiB after serialization; saved Parquet size is checked
  after writing. These are acceptance limits, not hard peak-memory/disk quotas.
- The deadline excludes database lookup and MinIO transfer. The executor is for
  this local learning environment, not a public multi-user SQL sandbox.
- 404: source absent; 409: source not ready or duplicate saved name; 413: oversized
  input; 422: request validation or controlled executor rejection (including timeout);
  503: storage/catalog unavailable; 500: other internal failures.

Object upload and metadata commit are not atomic. On confirmed unique-name
rejection, only the new object is removed. If commit confirmation is lost, the
object is retained and the 503 includes its table ID: check GET /tables/{id} before
retrying. Other failed uploads/registration/cleanup can leave unregistered objects;
automatic reconciliation is deferred. Save is not an idempotent operation.

## Database migration and verification

For a fresh database, db/init.sql includes saved_tables. Existing databases need
db/migrations/004_add_saved_tables.sql; **it was applied to this local database on
2026-09-14**. Do not recreate the database or rerun historical migration 003.

The automated suite passed: `python -m pytest -q` -> 140 passed, one existing
python_multipart pending-deprecation warning. The Python installation is available;
earlier missing-Python messages were caused by sandbox access restrictions.

`python scripts/verify_saved_tables.py` exercises upload, asynchronous processing,
truncated preview, full save, metadata read/list, duplicate rejection, blocked SQL,
and deriving/querying a second table. It deliberately retains a small sample dataset,
run, and two tables each time it runs. The live test passed, and querying the first
saved table after an API restart returned north=30 and south=5.

Retained walkthrough examples:

- Run: a221c34f-8519-4f1f-aa52-9ce0034d7c76
- Regional table: 649c6250-393a-436c-9081-d9779f406029
- Grand-total table: 9d3e23a7-4d3a-4dc3-a8cf-b68d7989651b

Session 021 stored-file downloads are implemented and live-verified. The full
suite now passes **176 tests**, with the same dependency deprecation warning.
The demo's downloaded original CSV matched all 86 source bytes; the processed
Parquet contained Alice=150, Bob=120, Charlie=180 and Dana=200.
Session 022 added 24 CSV export cases; the full suite now passes **200 tests**
(one existing dependency warning). Both CSV routes passed live checks against the
user's demo run and saved summary; overflow returned 422 and the catalog was unchanged.
Verified copies are in artifacts/csv-exports-_rhvspeu/. The 020-022 feature extension
is complete; deployment wrap-up remains separate.
The GUI and LAN verification remain later work. No commit, push, or PR was made.
