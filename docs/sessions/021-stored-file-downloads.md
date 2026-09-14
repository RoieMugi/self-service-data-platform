# Session 021 - Stored-file downloads

**Date:** 2026-09-14

**Status:** Implemented and verified.

## Objective and workflow

Complete stored-file downloads. During the Session 020 walkthrough, the user added
the saved-table Parquet download route, rebuilt the API, downloaded their summary,
and verified its values locally with DuckDB. The assistant then added its nine
automated tests (149 total passed). The user subsequently authorized implementing
and verifying both remaining download routes.

## Changes

- app/main.py: GET /uploads/{upload_id}/download and
  GET /processing-runs/{run_id}/download; shared bounded storage reader.
- Raw CSV download preserves bytes, strips filename path/control characters,
  and encodes the Unicode filename with a UUID fallback.
- Processing-output download requires a succeeded run and an artifact location.
- No new SQL execution, processing run or metadata record is created by download.
- test_file_downloads.py: 27 added cases; test_table_download.py: nine earlier cases.
- README and query guide updated with endpoints, limits and results.

## Verification

- Guided saved-table download: user edited download_saved_table() in main.py,
  rebuilt the API, downloaded aa20d66f-aa0e-4784-bbe0-7b6e5334e0d2.parquet, and
  read it locally with DuckDB: 4 / 650.0 / 162.5 / 200.0. Python source initially
  pasted into PowerShell was corrected by placing it in the editor instead.
- Added nine saved-table download tests: 149 total passed before the two additional
  file routes; these cover exact bytes, headers, readability, errors and cleanup.

- `python -m pytest -q`: **176 passed, 1 warning in 17.26s**.
- Existing python_multipart pending-deprecation warning remains.
- Rebuilt only the Compose API with `docker compose up -d --build --no-deps api`.
- Downloaded upload 246cbcbf-1fde-4acc-99dd-e6cb2b6e6c29: 86 bytes exactly matched
  csv_test_files/session20-customer-sales.csv.
- Downloaded run 3167cc91-5af4-4279-90ec-15dd04f8cd4a: 530-byte Parquet, independently
  read with DuckDB, contained four rows: Alice 150, Bob 120, Charlie 180, Dana 200.
- Verification copies retained in artifacts/file-downloads-sr7ljrt6/.
- No application data was modified or new processing submitted during verification.
- No commit, push, PR, database migration, Terraform apply or Kubernetes change.

## Limits and next step

Downloads buffer at most the configured limit plus one byte: 10 MiB raw CSV,
20 MiB Parquet. These are local learning limits, not streaming large-file support.
The processing download shares query-source validation and its existing error
wording. Stored-file download does not convert Parquet to CSV.

Next: Session 022 CSV query-result export. Then 1-2 deployment wrap-up sessions;
GUI, cross-file SQL joins and LAN verification remain later work.
