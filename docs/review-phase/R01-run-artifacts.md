# R01 - Run-specific processing artifacts

**Date:** 2026-11-14 (Asia/Jerusalem)
**Status:** Complete for the agreed local scope.

## Problem and change

Previously, every processing run for one upload wrote to
`<dataset_id>/<upload_id>/data.parquet`. A later run could replace the bytes
referenced by an earlier successful run. New runs now write to
`<dataset_id>/<upload_id>/<run_id>/data.parquet`. PostgreSQL continues to store
the selected key on each run, and query and download routes continue to read
that stored key. Existing run records and objects were not rewritten.

The owner changed key construction in `app/main.py`. The assistant updated two
existing test expectations and added a two-run regression test in
`test_health.py`. That test uses one upload, two run IDs, an in-memory object
store, and the processing-output download route to check that both outputs
remain separately readable.

## Session sequence

1. Reviewed Phase 1 records and the review roadmap, then traced processing
   submission, object-key construction, database completion, and artifact reads.
2. Agreed that each run needs a distinct output key while old records continue
   to resolve the key already stored in PostgreSQL.
3. The owner added `run_id` to the new key. The assistant added the regression
   test and updated the existing key expectations.
4. The owner ran focused tests and the full suite. The assistant's shell lacked
   a working Python installation, so the test results were shared from the
   owner's terminal.
5. A missing local `.env` initially prevented Compose from interpolating
   required variables. The owner copied `.env.example` to `.env`, confirmed the
   existing services, and rebuilt the API and worker with the changed code.
6. The owner checked database health, created a small dataset and upload,
   submitted two processing runs, compared their stored keys, and downloaded
   both results. An older run was also downloaded through its legacy key.
7. The assistant recorded the evidence in the roadmap, README, and session
   index, then tidied the changed test's formatting.

## Verification

- The owner reported a focused pytest run: 3 passed, 49 deselected, 1 warning.
- The owner reported the full suite: 201 passed, 1 warning in 38.09 seconds.
- The owner rebuilt the Compose API and worker, confirmed API database health,
  then processed one CSV upload twice. Runs
  `cfd6067d-3ca8-4bc1-916b-49747768eef7` and
  `4baf1ff2-5026-4c20-873b-ec4eef5e04b9` both succeeded. Their stored keys
  have separate run-ID directories. Both download routes returned 530-byte
  Parquet files.
- Existing run `3167cc91-5af4-4279-90ec-15dd04f8cd4a` retained its
  legacy key without a run-ID directory and downloaded a 530-byte file.
- The assistant checked `git diff --check` for the changed code and test;
  no whitespace errors were reported. The assistant's shell could not run
  pytest or Docker because Python and Docker were unavailable there. Runtime
  and pytest results above are owner-reported, not independently rerun.

## Limits and next step

The two live runs used the same CSV and processing code, so equal file sizes
do not establish byte differences. Distinct stored keys and successful reads
establish that the new runs have separate readable objects. Any historical
bytes overwritten before this change cannot be recovered without a backup.
No clean-clone full-stack run or fault injection was performed here.

Next: R02, a clean-environment full-stack verification and CI integration job.
