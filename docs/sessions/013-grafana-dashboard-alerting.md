# Session 013 - Grafana Dashboard and Alerting

**Date:** 2026-09-06

**Status:** Complete

## Objective

Turn the platform's Prometheus metrics into an operational dashboard and define
basic alerts for infrastructure failures and sustained API memory usage.

## What we built

- A Grafana service with persistent local storage.
- A provisioned Prometheus data source with a stable UID.
- A version-controlled operational dashboard with seven panels.
- Prometheus alert rules for processing infrastructure failures and sustained
  API memory usage.
- A reusable CSV fixture for live processing verification.

## Dashboard signals

- Processing-run totals by outcome.
- Recent processing outcomes.
- API CPU usage in CPU-core equivalents.
- API resident memory usage.
- Successful row throughput.
- Approximate 95th-percentile processing duration.
- Time since the last successful processing run.

## Concepts learned

- Grafana visualizes metrics stored by Prometheus.
- Provisioning makes dashboards and data sources reproducible from repository
  files.
- CPU seconds converted with `rate()` represent CPU-core equivalents.
- Process resident memory measures the FastAPI process, which currently includes
  synchronous DuckDB processing.
- Prometheus counters require observed samples before and after an increment for
  `increase()` to detect a change.
- Alert rules move through inactive, pending, and firing states.
- A firing alert does not send notifications without Alertmanager or a
  configured contact point.

## Design decisions

- Used built-in Python process metrics instead of cAdvisor because Docker
  Desktop exposed only broad WSL2 control groups, not reliable Compose-service
  labels.
- Excluded validation failures from infrastructure alerts.
- Required high memory to persist for five minutes before firing.
- Stored the dashboard as JSON and assigned the Prometheus data source a stable
  `prometheus` UID.
- Kept Grafana and Prometheus data in separate named volumes.

## Files changed

- `docker-compose.yml`
- `prometheus.yml`
- `prometheus-alerts.yml`
- `grafana/dashboards/data-platform-operations.json`
- `grafana/provisioning/dashboards/dashboard.yml`
- `grafana/provisioning/datasources/prometheus.yml`
- `csv_test_files/session13-demo.csv`
- `README.md`
- `docs/sessions/README.md`
- `docs/sessions/TIMELINE.md`
- `docs/sessions/013-grafana-dashboard-alerting.md`

## Verification

- `docker compose config --quiet` completed successfully.
- Grafana automatically provisioned its Prometheus data source and dashboard.
- A successful three-row CSV processing run updated the dashboard.
- A controlled MinIO outage returned HTTP 503 and incremented the
  `storage_failed` outcome.
- `PlatformProcessingInfrastructureFailure` entered the firing state.
- MinIO was restored and returned to healthy status.
- `python -m pytest -q` completed with 43 passing tests.

## Blockers

- None.

## Next checkpoint

Separate processing execution from the API by introducing an asynchronous job
queue and worker.
