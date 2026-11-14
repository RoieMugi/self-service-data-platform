# Query, save, and download data

Open [the local API documentation](http://127.0.0.1:8000/docs) after starting Compose. Every SQL request reads exactly one completed run or saved table, referred to in SQL as `dataset`. Catalog names are labels, not SQL table names. Cross-source joins and data-changing statements are not supported.

## Routes

| Method and route | Result |
| --- | --- |
| `POST /processing-runs/{run_id}/query` | Preview a successful run's Parquet artifact. |
| `POST /tables/{table_id}/query` | Preview a saved table. |
| `POST /processing-runs/{run_id}/tables` | Save a full SELECT result as a named Parquet table. |
| `POST /tables/{table_id}/tables` | Save a table derived from a saved table. |
| `GET /tables?limit=50&offset=0` | List saved tables, newest first; limit 1 to 100. |
| `GET /tables/{table_id}` | Read saved-table metadata and source IDs. |
| `GET /uploads/{upload_id}/download` | Download the original CSV bytes. |
| `GET /processing-runs/{run_id}/download` | Download a successful run's Parquet. |
| `GET /tables/{table_id}/download` | Download a saved table's Parquet. |
| `POST /processing-runs/{run_id}/query/csv` | Export a SELECT over a successful run as CSV. |
| `POST /tables/{table_id}/query/csv` | Export a SELECT over a saved table as CSV. |

Preview a result:

```json
{"sql": "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region ORDER BY region", "max_rows": 100}
```

Save the complete result using a separate request. Saving executes the SQL again; it does not persist a prior preview:

```json
{"name": "sales_by_region", "description": "Regional totals", "sql": "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region ORDER BY region"}
```

The response includes the table ID, source ID, SQL, row count, size, and creation time. Parquet is stored under `tables/{table_id}/data.parquet` in the curated bucket; PostgreSQL holds its metadata. The source remains unchanged. Empty results retain their schema. Names are unique within the saved-table catalog using case-sensitive PostgreSQL text equality.

### Safe save retries

For either save route, send an optional UUID in the `Idempotency-Key` header. If the response is lost, repeat the **same key and request body**: the API returns the same logical table. Reusing that key with a different source, name, description, or SQL returns HTTP 409. Without a key, a duplicate name also returns 409. If commit outcome cannot be confirmed, the API returns HTTP 503 with a table ID; check `GET /tables/{table_id}` before choosing a new request. An object write can still leave an unreferenced object, which the [read-only inventory](verification.md#object-inventory) can report.

### CSV export

Send a body such as `{"sql": "SELECT region, total FROM dataset ORDER BY region"}` to either `/query/csv` route. The response is a UTF-8 CSV attachment with headers and `X-Row-Count`. It re-executes the query but does not create a saved table or processing run. The request does not accept `max_rows`; use SQL `LIMIT` if you want fewer rows. Empty results include headers. A NULL is written as an empty CSV field, and CSV does not preserve the Parquet type schema.

## Limits and errors

- Exactly one parsed `SELECT`; at most 10,000 SQL characters and one source artifact per request. The executor disables external access after loading the selected file.
- Preview returns up to 100 rows by default or 1,000 when requested. `truncated` signals an extra row; it is not a count of all matching rows. Preview JSON is capped at 1 MiB.
- Save and CSV export return at most 100,000 rows and 20 MiB of output. They reject overflow rather than return a partial successful result. Input Parquet is capped at 20 MiB.
- The child process has a 10-second execution deadline, one DuckDB thread, a 256 MB engine memory setting, and no disk spill. These are application bounds, not hard operating-system memory or peak disk quotas. The deadline does not include database lookup or object transfer.
- `QUERY_CONCURRENCY_LIMIT` defaults to 2. It admits queries, saves, and CSV exports per API process, from lookup through transfer and execution. Excess concurrent requests receive HTTP 429. Separate API replicas would each have their own limit.
- Download limits are 10 MiB for original CSV and 20 MiB for Parquet. Downloads and CSV exports are buffered in memory.
- Typical errors: 404 for a missing source; 409 for a source that is not ready, duplicate name, or key conflict; 413 for an oversized input; 422 for invalid SQL, output overflow, or query timeout; 429 for admission pressure; 503 for unavailable storage or catalog.

This executor is designed for the local trusted learning environment. It is not an isolation boundary for arbitrary public users. The [main README](../README.md) describes how to reproduce the full workflow.
