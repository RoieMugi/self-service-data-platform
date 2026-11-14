# R02 - Clean-stack verification checkpoint

**Date:** 2026-11-14
**Status:** Partially verified; clean disposable-stack run pending.

The smoke script now checks the uploaded CSV bytes, processed Parquet rows, saved-table Parquet rows, and CSV export values. It waits for API/database readiness and reports POST error details. A focused Parquet-reader test and a separate disposable Compose integration job were added to CI.

The owner ran `python -m pytest -q`: **202 passed, 1 existing `python_multipart` pending-deprecation warning**. Against the owner's retained local Compose stack, smoke attempts reached successful upload, processing, and Parquet download, but did not complete. One query returned HTTP 422 with `Query exceeded the 10-second execution limit.` An earlier table save returned HTTP 422 without its response body captured; another attempt saw an HTTP connection close during raw download. The API and worker remained running, and RabbitMQ later reported healthy. A later idle `docker stats --no-stream` snapshot showed the separate Kubernetes control plane using about 1 GiB and 44% CPU of a 3.64 GiB Docker allocation. This suggests possible local contention but does not establish the cause during a failed query.

**Acceptance still needed:** Run the new CI integration job or an equivalent clean, isolated Compose stack; verify the full smoke flow and retained logs. Do not delete the owner's existing local volumes to obtain this evidence. R02 is not marked complete, and no clean-clone claim should be made from the current results.

**Later retained-stack result (2026-11-14):** After migration 005 and rebuilding API, worker, and reconciler, the smoke script passed the normal upload, processing, query, save, CSV export, and download flow. See the [R06–R10 checkpoint](R06-R10-implementation.md) for IDs. This confirms the current local stack works, but it was not a clean environment and does not close R02.
