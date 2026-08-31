# Session 008 - DuckDB CSV-to-Parquet Processing

**Date:** 2026-08-31

**Status:** Complete

## Objective

Transform a registered raw CSV upload into curated Parquet with DuckDB and store
the result in MinIO.

## What we built

- A persistent `curated` MinIO bucket alongside the existing `raw` bucket.
- Explicit `MINIO_RAW_BUCKET` and `MINIO_CURATED_BUCKET` configuration.
- DuckDB 1.5.5 as the local analytical processing engine.
- `POST /uploads/{upload_id}/process` for synchronous CSV-to-Parquet processing.
- PostgreSQL upload lookup by UUID.
- Raw-object download and connection cleanup.
- Temporary-file CSV processing with automatic cleanup.
- Curated Parquet upload under
  `{dataset_id}/{upload_id}/data.parquet`.
- Processing responses containing dataset ID, upload ID, object key, format, and
  row count.
- Automated tests for the processing helpers, successful orchestration, and
  important failure paths.

## Concepts learned

- PostgreSQL and FastAPI form the metadata control plane.
- MinIO holds raw and curated objects in the data plane.
- DuckDB provides compute without requiring a distributed processing system.
- Buckets represent lifecycle zones, while object-key prefixes organize logical
  datasets and uploads.
- CSV is row-oriented and weakly typed; Parquet is typed, compressed, and
  column-oriented for analytical workloads.
- Temporary local files can safely bridge byte streams and file-oriented tools
  when their lifetime and size are bounded.
- External response streams must be closed and returned to their connection
  pool.
- Safe client errors and detailed server logs serve different purposes.
- Real data commonly contains a UTF-8 byte order mark and mixed line endings.
  The processor removes an optional BOM and uses DuckDB non-strict dialect
  handling without silently ignoring bad rows.

## Processing flow

```text
POST /uploads/{upload_id}/process
    -> look up upload metadata in PostgreSQL
    -> download the raw CSV from MinIO
    -> parse and convert it with DuckDB
    -> upload Parquet to the curated MinIO bucket
    -> return the curated object key and row count
```

## Design decisions

- Processing targets a physical upload UUID rather than a logical dataset name.
- `raw` and `curated` are separate buckets because they have different lifecycle
  roles.
- Dataset and upload UUIDs organize objects inside each bucket; buckets are not
  created per table.
- Processing remains synchronous for this checkpoint. Persistent processing-run
  history and a worker are deferred to Checkpoint 008.
- The curated key is deterministic, so reprocessing the same upload replaces the
  same logical output instead of creating ambiguous duplicates.
- The initial 10 MiB input limit makes in-memory transfer and temporary local
  processing acceptable for the local MVP.

## Files changed

- `app/main.py`
- `docker-compose.yml`
- `requirements.txt`
- `test_health.py`
- `README.md`
- `docs/sessions/README.md`
- `docs/sessions/TIMELINE.md`
- `docs/sessions/008-duckdb-csv-to-parquet.md`

## Verification

- `docker compose config` rendered valid configuration with raw and curated
  bucket settings.
- `python -m pytest -q` completed with 20 passing tests and one third-party
  Starlette pending-deprecation warning.
- The API image rebuilt successfully with DuckDB 1.5.5.
- PostgreSQL resolved upload
  `174ddb4c-2b76-4f8d-821a-aff656282d1b` to its raw MinIO object.
- Live processing returned HTTP 200, a curated Parquet key, and `row_count: 3`.
- `mc stat` confirmed the Parquet object in the `curated` bucket with content type
  `application/vnd.apache.parquet`.
- DuckDB read the stored Parquet object and returned
  `[(1, 100), (2, 250), (3, 175)]`.
- A regression test covers the UTF-8 BOM and mixed-line-ending input discovered
  during live verification.

## Blockers resolved

The live CSV initially failed DuckDB dialect detection. Inspection showed a UTF-8
BOM and mixed `LF`/`CRLF` line endings. We removed the optional BOM and enabled
DuckDB's non-strict dialect handling while retaining row-level errors.

## Next checkpoint

Track processing runs, validation results, curated output metadata, status, and
failures in PostgreSQL.
