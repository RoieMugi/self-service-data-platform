# Session 011 - Operational Metrics with Prometheus

**Date:** 2026-09-02

**Status:** Complete

## Objective

Add basic operational visibility so operators can measure aggregate processing
behavior over time, while PostgreSQL continues to store detailed per-run state.

## What we built

- A Prometheus-compatible `GET /metrics` endpoint in FastAPI.
- Four custom processing metric families:
  - `platform_processing_runs_total{outcome=...}`
  - `platform_processing_duration_seconds{outcome=...}`
  - `platform_processed_rows_total`
  - `platform_last_successful_processing_timestamp_seconds`
- Controlled outcome labels: `succeeded`, `validation_failed`,
  `storage_failed`, and `internal_failed`.
- A Prometheus 3.14.0 service under Docker Compose.
- A 15-second scrape configuration targeting `api:8000/metrics`.
- Persistent Prometheus storage in the `prometheus_data` Docker volume.

## Concepts learned

- Tests verify expected behavior; health checks report current reachability;
  durable run records describe individual executions; metrics summarize behavior
  over time.
- Counters measure totals, histograms measure distributions such as duration,
  and gauges represent values that can be replaced, such as a timestamp.
- Prometheus pulls metrics by scraping HTTP endpoints and stores timestamped
  samples in its own time-series database.
- Metric labels must use small controlled value sets. Run IDs, dataset IDs,
  filenames, and error messages would create high-cardinality time series.
- A monotonic clock is appropriate for elapsed duration, while Unix time is
  appropriate for a real completion timestamp.
- Application metrics exist in process memory; Prometheus provides external
  collection and historical retention.

## Design decisions

- Keep the initial contract focused on processing behavior rather than measure
  every endpoint.
- Record exactly one outcome for each established processing attempt.
- Do not count missing-upload requests as processing attempts.
- Update row volume and last-success time only after PostgreSQL confirms a
  successful run.
- Group raw-download and curated-upload problems as `storage_failed`, retaining
  the detailed distinction in logs and processing-run records.
- Hide `/metrics` from the public OpenAPI schema because it is an operational
  endpoint.
- Pin both `prometheus-client` and the Prometheus container version.

## Files changed

- `app/main.py`
- `test_health.py`
- `requirements.txt`
- `docker-compose.yml`
- `prometheus.yml`
- `README.md`
- `docs/sessions/README.md`
- `docs/sessions/TIMELINE.md`
- `docs/sessions/011-operational-metrics.md`

## Verification

- `python -m pytest -q` completed with 33 passing tests and one existing
  third-party Starlette pending-deprecation warning.
- `docker compose config` validated the combined Compose model.
- `promtool check config /etc/prometheus/prometheus.yml` reported success.
- `docker compose up -d --build` rebuilt the API and started Prometheus.
- Prometheus reported `up{job="data-platform-api"} = 1` for `api:8000`.
- A live successful run processed three rows in approximately 1.18 seconds.
- Prometheus stored the successful count, row total, duration, and last-success
  timestamp.
- A live empty-file run returned HTTP 422 and produced a
  `validation_failed` sample.

## Blockers

- None.

## Next checkpoint

Add structured logging and correlation identifiers so operators can connect
aggregate metrics to the diagnostic events for a specific request, upload, or
processing run.
