# Session 012 - Structured Logging and Correlation IDs

**Date:** 2026-09-02

**Status:** Complete

## Objective

Add request-level correlation and structured diagnostic events so operators can
trace an individual HTTP request, upload, and processing run while Prometheus
continues to provide aggregate behavior over time.

## What we built

- HTTP middleware that accepts a valid UUID from `X-Correlation-ID` or generates
  a UUID when the header is absent or invalid.
- An `X-Correlation-ID` response header containing the effective identifier.
- A JSON log formatter and dedicated `platform.api` logger.
- One `http_request_completed` event per response with method, stable route
  template, status code, correlation ID, and duration.
- Processing events for `processing_started`, `processing_succeeded`, and
  `processing_failed`.
- Controlled outcomes aligned with metrics: `succeeded`, `validation_failed`,
  `storage_failed`, and `internal_failed`.

## Concepts learned

- Python's standard `logging` library creates records, filters them by severity,
  formats them, and sends them through handlers.
- JSON logs are still text, but their fields can be parsed and searched reliably.
- A correlation ID connects request events; a run ID identifies one durable
  processing attempt.
- Stable route templates avoid unbounded values from UUID-based URLs.
- `WARNING` represents expected validation failures; storage and internal
  platform failures use `ERROR`.

## Design decisions

- Preserve valid caller-supplied UUIDs and replace missing or invalid values.
- Return the effective identifier in every response.
- Emit one request-completion event rather than separate start/end noise.
- Log processing start only after PostgreSQL creates the running record.
- Allow a failure event without a run ID only when run creation itself fails.
- Serialize an allowlist of context fields and exclude bodies, CSV contents,
  credentials, and authorization data.

## Files changed

- `app/main.py`
- `test_health.py`
- `README.md`
- `docs/sessions/README.md`
- `docs/sessions/TIMELINE.md`
- `docs/sessions/012-structured-logging.md`

## Verification

- `python -m pytest -q` completed with 43 passing tests and one existing
  Starlette pending-deprecation warning.
- `docker compose config` validated the Compose model.
- `docker compose up -d --build` rebuilt and started the API.
- A live `GET /health` returned HTTP 200 and echoed the supplied correlation ID.
- A live processing attempt returned HTTP 422 for an upload with no data rows.
- Its start, failure, and HTTP completion events shared the same correlation ID.

## Blockers

- None.

## Next checkpoint

Add Grafana dashboards and basic alerting over the Prometheus metrics.
