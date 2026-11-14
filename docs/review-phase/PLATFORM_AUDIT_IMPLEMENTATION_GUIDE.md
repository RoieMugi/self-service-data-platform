# Self-Service Data Platform — Technical Audit & Implementation Guide

**Repository:** https://github.com/RoieMugi/self-service-data-platform
**Audit date:** 2026-11-11
**Audited revision:** `97421c2ad6461258ab6a0f23f8e8111be648c8ab`
**Audience:** Project owner, reviewers, Codex / other AI coding agents
**Status at audit:** **NO-GO for active résumé promotion until pre-publication checks are completed**; this is **not** a prohibition on hosting the source publicly (the repository was already public).

> This document is an actionable summary of the technical audit discussion, not a byte-for-byte chat transcript. Findings are grounded in repository inspection and available CI evidence, but most runtime failure scenarios were **not reproduced**. Re-check all line numbers and assumptions against the current branch before editing.

## 1. Project and scope

The project is a **local learning / portfolio prototype** for self-service batch data processing:

- FastAPI: API for dataset registration, uploads, processing submissions, queries, downloads.
- PostgreSQL: metadata and durable processing-run states.
- MinIO: raw CSV and curated Parquet object storage.
- RabbitMQ: queued work delivery.
- Python worker and DuckDB: CSV-to-Parquet processing; DuckDB also supports bounded query previews and exports.
- Prometheus/Grafana: metrics and dashboards.
- Docker Compose: local full stack. Terraform/Kubernetes directories: **separate API-only learning labs**, not complete production deployments.

The repository explicitly documents that it has no API authentication, uses disposable local demo credentials, and does not offer a secure public multi-user SQL sandbox. **Do not silently expand scope to production readiness.**

## 2. Evidence and verification boundaries

- GitHub `main` was inspected at the commit above; 16 commits were listed at audit time.
- GitHub Actions run https://github.com/RoieMugi/self-service-data-platform/actions/runs/43012594834 completed successfully: **200 tests passed, 1 warning** (2026-11-11).
- CI runs Python pytest with mocked external dependencies; it **does not** launch the full Docker Compose stack.
- Actual Docker image builds, full Compose startup, RabbitMQ/MinIO/PostgreSQL fault injection, and Kubernetes/Terraform deployment were **not executed during this audit**.
- No confirmed real private cloud/API keys were found in inspected files. **A comprehensive history-aware secret scan was not completed.** Historical hardcoded *demo* credentials were verified.
- All original findings are hypotheses to revalidate against subsequent code changes; a 'verified' code finding does not imply that its impact was reproduced in a running stack.

## 3. Prioritized action plan

### Gate A — Before promoting repository on résumé

- [ ] **P0 / H-03: Make curated Parquet keys unique per processing run.**
- [ ] **P0 / M-02: Run a clean-clone full-stack Compose smoke test** and record reproducible evidence.
- [ ] **P0 / M-05: Complete a history-aware secret scan**; rotate any real credentials if detected.
- [ ] **P0: Confirm README honestly describes local-only scope and known reliability limitations.**

These are publication gates from the audit. They do not require implementing production-grade authentication, an outbox, or Kubernetes orchestration.

### Gate B — Valuable next reliability iteration

- [ ] **H-01: Recovery for worker crashes and stuck `running` rows.**
- [ ] **H-02: Transactional outbox or equivalent reliable DB-to-broker handoff.**
- [ ] **M-04: Reconciliation for uncertain upload commits and object-store metadata divergence.**
- [ ] **M-02: Add real integration coverage to CI.**

### Gate C — Production-oriented / later enhancements

- [ ] **H-04: Authentication, authorization and request throttling** before any shared/network deployment.
- [ ] **M-01: OS-enforced query isolation and application-wide concurrency limits.**
- [ ] **M-03: Processing timeout, memory/output bounds and streaming.**
- [ ] **L-01: Improve image/dependency reproducibility.**
- [ ] **L-02: Kubernetes readiness/liveness probes.**
- [ ] **L-03: Versioned migration tooling and upgrade tests.**

## 4. Findings and implementation specifications

### H-01 — Interrupted jobs remain stuck in `running`

**Severity:** High for reliability. **Status:** Verified code-path limitation; crash scenario not run.
**Evidence:** `app/main.py` lines ~606–625 and ~1026–1044 at audited commit. Conditional claim permits only `queued`; code explicitly states `running` rows are not reclaimed. `app/worker.py` ~26–73 acknowledges terminal outcomes and leaves uncertain outcomes unacknowledged.

**Failure scenario:** Worker claims run; process dies; RabbitMQ redelivers; the database row is already `running`, so a second claim fails and no recovery happens.

**Suggested implementation:** Introduce `lease_expires_at`, `attempt_count`, and a unique execution/claim token. Heartbeat long-running jobs; reclaim expired leases; guard final updates using the token; cap attempts and record terminal failure. Consider a periodic reconciler.

**Acceptance criteria:**
1. Crash simulation after claim produces a recoverable run.
2. Two workers cannot simultaneously finalize the same execution token.
3. Expired attempts can be retried with bounded attempts; terminal runs are not reprocessed.
4. Tests cover broker redelivery and database state transitions.

### H-02 — Database-to-RabbitMQ publication is not atomic

**Severity:** High. **Status:** Verified architecture; failure not injected.
**Evidence:** `app/main.py` ~945–1004; `app/messaging.py` ~17–47. Database row is committed separately from broker publish; publisher confirms do not make a distributed transaction.

**Failure scenario:** Queued row commits; RabbitMQ publish fails; no message exists to drive processing.

**Suggested implementation:** Transactional outbox row created in same DB transaction as processing run. Publisher scans undelivered outbox records, publishes with confirms, and marks delivery; duplicate delivery remains possible and workers must be idempotent. Add stale queued-run detection/reconciliation.

**Acceptance criteria:**
1. Simulate broker outage immediately after DB commit; event is eventually delivered after recovery.
2. Duplicate publish does not create duplicate successful execution.
3. Pending outbox state is observable; failure is surfaced rather than silently lost.

### H-03 — Multiple processing runs overwrite the same Parquet key

**Severity:** High. **Status:** Verified key construction; concurrency/data difference not reproduced.
**Evidence:** `app/main.py` ~1184–1194. Key uses `dataset_id/upload_id/data.parquet` and omits `run_id`.

**Failure scenario:** Two runs for one upload target the same object, so later writes can replace bytes associated with earlier metadata.

**Suggested implementation:** Change to `dataset_id/upload_id/run_id/data.parquet`; ensure all downstream reads and metadata references use the persisted run-specific key. Do **not** blindly rewrite existing keys without considering old data. Add migration/compatibility behavior if needed.

**Acceptance criteria:**
1. Two runs for the same upload have different object keys.
2. Reading either run resolves its own artifact.
3. Re-running a different run does not mutate the first run's object.
4. Unit test plus MinIO integration test.

### H-04 — No API authentication / authorization

**Severity:** High **if network-exposed**; accepted local prototype limitation. **Status:** Verified.
**Evidence:** `app/main.py` endpoint definitions; `docker-compose.yml` ~22–26 binds API to `127.0.0.1`; README describes unauthenticated local use.

**Suggested implementation:** For now preserve localhost binding and clear warning. Before shared deployment add identity verification, dataset ownership checks, role/permission enforcement, audit logging and rate limits.

**Acceptance criteria for current portfolio:** Documentation says explicitly not for public/shared deployment; Compose ports remain loopback-bound. **Do not build a full IAM system just to satisfy the portfolio gate.**

### M-01 — Query limits are not OS-enforced

**Severity:** Medium. **Status:** Verified limitation; no successful escape/exhaustion demonstrated.
**Evidence:** `app/query_executor.py` ~37–147; `docs/query-tables.md` ~85–111.

Current defenses include a 10-second child deadline, input/output limits, single-SELECT validation, DuckDB memory settings and restricted external access. However, the DuckDB memory setting is not an OS RSS cap; there is no global concurrent query limit or disk quota; output checks happen after writing.

**Suggested implementation:** Bound simultaneous child processes, apply OS/container CPU/RAM/tmpfs limits, and validate behavior with resource-exhaustion tests. Keep local executor protections even if isolation is added.

### M-02 — CI lacks real end-to-end integration

**Severity:** Medium. **Status:** Verified.
**Evidence:** `.github/workflows/tests.yml` ~11–30; passing run https://github.com/RoieMugi/self-service-data-platform/actions/runs/43012594834.

**Suggested implementation:** A second workflow or job that starts Compose using disposable env values, waits for health, uploads a small CSV, creates a run, polls terminal state, queries result, downloads artifact, checks expected rows, and tears down volumes. Keep unit tests as fast first gate.

**Acceptance criteria:** From a clean clone, documented commands pass without pre-existing volumes, host secrets, or manual database setup. Store CI logs as evidence. Test failure must fail the workflow.

### M-03 — CSV processing has incomplete runtime resource bounds

**Severity:** Medium. **Status:** Verified design limitation; no exhaustion demonstrated.
**Evidence:** `app/main.py` ~462–494, ~744–773, ~1124–1127. Input CSV max 10 MiB; worker transforms and materializes full Parquet bytes in memory; no dedicated worker transformation deadline or OS resource limit.

**Suggested implementation:** Worker timeout, memory/CPU caps, output-size checks, and streaming for larger artifacts. Test pathological but bounded inputs. Preserve simple design for local MVP if explicitly deferred.

### M-04 — Ambiguous DB commit can leave dangling metadata

**Severity:** Medium. **Status:** Verified failure path; not reproduced.
**Evidence:** `app/main.py` ~829–876; source comments acknowledge ambiguous commit confirmation. MinIO upload precedes DB insert; exception path attempts object deletion.

**Failure scenario:** DB commits but response is lost; cleanup deletes object referenced by committed metadata.

**Suggested implementation:** Track pending/committed upload states and reconcile by stable ID. Avoid destructive cleanup when commit status is uncertain. Add fault-injection test.

### M-05 — Historical demo credentials remain in Git

**Severity:** Medium as a hygiene concern; not a confirmed private-secret leak. **Status:** Verified historical values.
**Evidence:** Prior `docker-compose.yml` at commit `a26342c`; current `.env.example` lines ~1–11 at audited commit. Latest Compose uses environment interpolation and localhost bindings.

**Suggested implementation:** Run Gitleaks or equivalent across **all history**, review any matches, and rotate credentials **only if used beyond disposable local demos**. Do not claim a clean scan without recording the scanner and result. Avoid rewriting history merely to remove known harmless demo values.

### L-01 — Reproducibility pinning is incomplete

**Severity:** Low. **Status:** Verified.
**Evidence:** `Dockerfile` ~1–6 (`python:3.11-slim`), `docker-compose.yml` (`postgres:15`, `rabbitmq:4-management`), `requirements.txt` has pinned direct dependencies but not a full resolved lock.

**Suggested implementation:** Consider image digests, dependency locking, and automated updates. Balance maintenance burden against local portfolio needs.

### L-02 — Kubernetes API lab lacks probes

**Severity:** Low. **Status:** Verified.
**Evidence:** `kubernetes/api-deployment.yml` ~16–29; `kubernetes/README.md` ~83–86 notes lack of probes.

**Suggested implementation:** Add liveness and readiness probes with appropriate semantics. Lab is API-only, not a full stack deployment.

### L-03 — Database migrations are manual

**Severity:** Low. **Status:** Verified.
**Evidence:** `db/migrations/001...004`; `db/init.sql` runs only on first initialization; README and session docs describe manual upgrades.

**Suggested implementation:** Introduce a migration version table and migration runner (e.g., Alembic or a lightweight SQL migration tool). Test fresh install and upgrade from an older schema; never blindly reapply migration 003.

## 5. Security and operational guardrails

- Treat `.env.example` values as **disposable demo credentials**. Never commit a populated `.env`, real keys, Terraform state, database dumps, or private datasets.
- `127.0.0.1` host-port bindings reduce exposure, but do **not** provide authentication for users/processes already able to reach the local service.
- `MINIO_SECURE=false` and unencrypted broker URLs are acceptable only for this explicitly local demonstration; reconsider for deployment across hosts.
- RabbitMQ durability, persistent messages, publisher confirms, and manual ACK are helpful but **do not** guarantee exactly-once processing or recovery from every DB/broker split failure.
- Named Docker volumes preserve local data across restarts but are **not backups**.
- Treat Terraform and Kubernetes lab claims separately from the Compose-based complete application.

## 6. Suggested implementation order for a coding agent

1. **Read-only baseline:** `git status`, current commit, README, Compose, affected code, tests; reproduce the relevant issue with a failing test before changing it when practical.
2. **H-03 artifact key:** Make the smallest safe change; update reads, tests, docs; run unit tests and a MinIO integration test.
3. **Clean-clone smoke test:** Document and execute Compose startup + full data path; do not assume historical tests still apply.
4. **Historical secret scan:** Use an appropriate scanner, inspect findings, record results without printing any discovered real secrets.
5. **Update README:** Explain scope, local-only security assumptions, exact tested commands, and deferred reliability work.
6. **Optional Phase 2:** H-01 recovery, H-02 outbox, M-04 reconciliation, then query/worker resource isolation.

## 7. Definition of done for each change

Every PR/task should provide:

- Issue/finding ID and why it matters.
- Exact code changes and affected files.
- A test that fails on the previous behavior (where practical).
- Unit/integration test results with commands and exit status.
- Compatibility considerations for existing local volumes/artifacts.
- README/docs update if behavior or setup changed.
- Explicit remaining limitations and follow-up tasks.

Avoid large unrelated refactors; do not add Kafka, Kubernetes, IAM, or other infrastructure without a concrete requirement.

## 8. Copy-paste prompt for Codex / coding agent

> You are working in `RoieMugi/self-service-data-platform`. Read `PLATFORM_AUDIT_IMPLEMENTATION_GUIDE.md` first. The audit references commit `97421c2ad6461258ab6a0f23f8e8111be648c8ab`, so **verify each issue against current HEAD**; line numbers may have changed. This is a local portfolio MVP, not a production service. Start with the **Gate A** checklist. First inspect and report the current state and propose a minimal change plan; do not edit until I approve the plan. For each approved task, add regression tests, run available tests, report what you did and did not verify, and preserve existing user data and Git history. Do not claim Docker/integration behavior works unless actually tested. Do not expose secrets or commit local `.env` files. Avoid unrelated architectural changes.

## 9. Final decision from audit

**NO-GO for active résumé promotion until:** (1) run-specific curated keys are implemented/tested, (2) the exact current full stack passes a clean-clone smoke test, and (3) a history-aware secret scan is completed. After these, **GO for an explicitly labeled local portfolio prototype**, assuming no new blockers appear. Production/public service deployment remains **NO-GO** without additional security and reliability work.

---

**Source of this document:** User-requested export of the ChatGPT pre-publication audit and follow-up implementation advice. It is an implementation handoff, **not** a verbatim transcript or a claim of independently executed live infrastructure tests.
