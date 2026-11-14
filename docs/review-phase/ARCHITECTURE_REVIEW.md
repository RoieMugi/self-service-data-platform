# Self-Service Data Platform — Architecture Review & Implementation Roadmap

**Review date:** 2026-11-11
**Repository:** https://github.com/RoieMugi/self-service-data-platform
**Audience:** Project owner, reviewers, and AI coding agents
**Status:** Advisory review; no repository changes made
**Scope:** Portfolio/local learning MVP, not a production readiness certification

> **Agent instruction:** This is a review and implementation backlog, NOT a statement that proposed changes already exist. Inspect current code, tests, and documentation before editing. Do not implement the entire roadmap at once. Start with one scoped change, propose a design, identify tests, and request approval. Preserve working API behavior unless a change is explicitly approved.

## 1. Executive verdict

The repository documents a functioning local batch-data workflow: dataset registration and CSV upload via FastAPI, PostgreSQL metadata, MinIO raw and curated objects, RabbitMQ-backed asynchronous worker processing, DuckDB CSV-to-Parquet conversion and bounded queries, saved derived tables, downloads, and Prometheus/Grafana observability.

**Provisional architecture score: 7/10** for a Junior/Mid Data Platform Engineer portfolio MVP, based on configuration, schema, and project documentation. This is not a full source audit or independent runtime verification.

**Central challenge:** Is this a reusable self-service platform, or a CSV-processing application built with platform technologies? It provides useful self-service operations for technical API consumers, but does not yet offer multi-user ownership, access controls, general catalog queries, cross-dataset joins, or a broad ingestion abstraction. Describe it accurately as a **local self-service batch data platform prototype**.

**Top risks:** (1) stranded `running` jobs after worker crashes, (2) non-atomic PostgreSQL run creation and RabbitMQ publication, (3) unbounded aggregate query concurrency, (4) non-idempotent saved-table creation and orphaned objects, (5) metadata/artifact divergence.

**Engineering principle:** Prioritize correctness and recoverability over adding Kafka, Spark, Kubernetes to the full pipeline, or other new infrastructure.

## 2. Evidence and confidence

Retrieved directly from the repository during review:

- [README.md](https://github.com/RoieMugi/self-service-data-platform/blob/main/README.md): system scope, explicit limitations, architecture and setup.
- [docker-compose.yml](https://github.com/RoieMugi/self-service-data-platform/blob/main/docker-compose.yml): PostgreSQL, MinIO, RabbitMQ, API, worker, Prometheus, Grafana; loopback port bindings; persistent named volumes; worker runs `python -m app.worker`.
- [db/init.sql](https://github.com/RoieMugi/self-service-data-platform/blob/main/db/init.sql): datasets, uploads, processing_runs, saved_tables; metadata keys, state constraints, and parent references.
- [docs/query-tables.md](https://github.com/RoieMugi/self-service-data-platform/blob/main/docs/query-tables.md): query/save/export endpoints, SQL execution restrictions, limits, failure and cleanup semantics.
- [PROJECT_HISTORY.md](https://github.com/RoieMugi/self-service-data-platform/blob/main/PROJECT_HISTORY.md): documented queue behavior, worker acknowledgment/claim behavior, failure limitations, monitoring.
- [docs/sessions/023-deployment-wrap-up.md](https://github.com/RoieMugi/self-service-data-platform/blob/main/docs/sessions/023-deployment-wrap-up.md): deployment lab scope and reported verification.

**Evidence limits:** No complete line-by-line source audit, fresh test execution, fault injection, or independent validation of the reported 200 tests was performed. Session 023 reports no new pytest run; 200 passing tests were reported for Session 022. Agent must confirm behavior in current source before implementing changes. Findings marked *documented* below reflect repository documentation, not newly reproduced experiments.

## 3. System architecture

```text
API consumer
   |
   v
FastAPI ----------------> PostgreSQL (datasets, uploads, runs, saved tables)
   |  \
   |   +---------------> MinIO (raw CSV, curated Parquet)
   |
   +-------------------> RabbitMQ (processing_runs queue)
                                |
                                v
                          Python worker
                          |        |
                          v        v
                       DuckDB    PostgreSQL / MinIO

FastAPI + worker metrics ---> Prometheus ---> Grafana
```

The API also executes bounded DuckDB-backed preview, saved-table and CSV-export queries. Terraform and Kubernetes directories are **separate API-only learning labs**, not deployment definitions for the complete data platform.

### Technology decisions and challenges

| Technology | Why it is defensible | What to challenge |
|---|---|---|
| PostgreSQL | Transactions and constraints for durable relational metadata/run state | DB state is not proof that MinIO objects exist; consider artifact reconciliation |
| MinIO | S3-compatible raw/curated storage, independent binary artifacts | More operations than local filesystem; artifact integrity and coordinated backup |
| DuckDB | Single-node SQL/Parquet analytics without Spark overhead | Engine memory setting is not an OS cap; aggregate concurrency and transfers matter |
| FastAPI | Simple metadata/control-plane API | Query execution shares API resources; define end-to-end limits |
| RabbitMQ | Async delivery, acknowledgments, decoupled worker | Dual-write, redelivery, stuck claims; PostgreSQL queue could be simpler for this scale |
| Worker | HTTP request need not remain open during processing | Crash recovery and safe retries are incomplete |
| Prometheus/Grafana | Operational insight and reproducible dashboards | Observability cannot substitute for recovery; notifications are deferred |

**Alternative architecture worth discussing:** FastAPI + PostgreSQL (including `FOR UPDATE SKIP LOCKED` job claiming) + DuckDB + local filesystem/object storage. This removes RabbitMQ and possibly MinIO, but teaches fewer message-delivery/object-storage failure modes. Do not refactor solely for minimal component count; make the learning objective explicit.

## 4. Findings — current state vs recommendations

### F1 — Worker crash can strand `running` runs (HIGH; MVP)

**Documented:** Worker conditionally claims `queued -> running`. RabbitMQ delivery is acknowledged after terminal processing. If a worker dies after claim, the run can remain `running` indefinitely; restart does not recover it. See `PROJECT_HISTORY.md` → *Queued-run preparation*.

**Failure scenario:** Worker claims run; process terminates before completion; message may be redelivered, but claim rejects the already-running run.

**Recommendation:** Design expiring claims/leases, attempt counters, bounded retry policy, and a recovery mechanism. Prevent stale workers from writing results after another worker takes ownership (fencing/claim token). Avoid blindly changing `running` back to `queued` while the old worker might still be active.

**Acceptance tests:**
- Kill worker after DB claim; demonstrate deterministic eventual recovery or a documented terminal failure outcome.
- Re-deliver the same message; only one active owner can finalize the run.
- Simulate old worker resuming after lease expiry; stale owner cannot overwrite newer result.
- Repeated failures stop at a documented retry limit.
- Normal successful and validation-failure paths still pass.

### F2 — Database/queue dual-write is not atomic (HIGH; MVP)

**Documented:** API creates queued run in PostgreSQL and publishes a persistent RabbitMQ message with publisher confirms/mandatory routing. On unconfirmed publish, API returns 503 with run ID, but a queued record can remain without guaranteed delivery. No outbox or automatic recovery.

**Recommendation:** Consider a **transactional outbox**: write run + publication intent in one PostgreSQL transaction; independent publisher sends to RabbitMQ and marks intent delivered after confirmation. Publication may repeat; consumer must remain idempotent. For an intentionally small MVP, a tested reconciliation/republish command is a narrower acceptable alternative.

**Acceptance tests:**
- RabbitMQ unavailable at submission: no silently abandoned job; retry/reconciliation works.
- Publisher crashes after broker confirmation but before marking outbox delivered: duplicate publication is safe.
- Database transaction rolls back: no committed run/outbox intent.
- Submission responses and status polling explain uncertain delivery clearly.

### F3 — No application-wide query concurrency limit (HIGH; MVP)

**Documented:** One SELECT, <=10,000 SQL characters, 20 MiB input, 10-second child deadline, one DuckDB thread, 256 MB DuckDB engine budget, no disk spill; preview up to 1,000 rows; save/export up to 100,000 rows and bounded output. `docs/query-tables.md` explicitly states no global query concurrency limit. Engine budget is not process memory cap; deadline excludes DB lookup/MinIO transfer.

**Recommendation:** Introduce bounded admission control (e.g., process-wide semaphore for local single API instance), clear overload response, and measurable end-to-end request behavior. If moving to multiple API instances later, process-local semaphore is insufficient; use shared admission or isolated query service.

**Acceptance tests:**
- Concurrent requests above configured limit are queued for bounded time or rejected consistently.
- Slots are released after success, validation error, timeout, and cancellation.
- Measure total latency including object transfers, not just DuckDB child execution.
- Document limits as workload controls, not hard process memory guarantees.

### F4 — Saved-table creation is non-idempotent and cross-system non-atomic (MEDIUM; MVP)

**Documented:** Saved table writes Parquet to MinIO and metadata to PostgreSQL; object and commit are not atomic. On unique-name rejection, cleanup is attempted; lost commit confirmation can leave uncertain outcome; no automatic reconciliation. Save operation is explicitly non-idempotent.

**Recommendation:** Define stable operation identifiers/idempotency keys and staged-to-committed artifact lifecycle; ensure cleanup/reconciliation handles unregistered objects. Decide whether retries should return existing saved table or a conflict, and document it.

**Acceptance tests:**
- Same idempotency key repeated after timeout yields one logical saved table.
- Simulated MinIO success + DB commit failure is detectable and recoverable.
- Unique-name conflict cannot delete a previously committed object.
- A retried request after unknown commit result can discover the original outcome.

### F5 — Metadata does not guarantee artifact integrity (MEDIUM; MVP)

**Verified schema:** `uploads` and `saved_tables` reference object keys; no content checksum field in inspected schema. `processing_runs` stores curated object key. Object existence/integrity is not transactionally coupled to PostgreSQL.

**Recommendation:** Introduce checksum/size verification where appropriate, artifact lifecycle states, and a small reconciliation report for missing referenced objects and orphaned objects. For MVP, read-only audit/reporting may be enough before automatic deletion.

**Acceptance tests:**
- Deliberately delete a referenced object: system reports a controlled missing-artifact state.
- Create an orphan object: audit identifies it without deleting unrelated files.
- Validate checksum/size mismatch when integrity metadata exists.

### F6 — Self-service abstraction is narrow (MEDIUM; positioning/MVP)

**Documented:** Users can register CSV, submit runs, poll status, query one selected artifact as `dataset`, save derived tables, and download CSV/Parquet. No cross-table joins, multi-user ownership, authorization, or UI.

**Recommendation:** Keep scope honest. Document personas, a concrete end-to-end user journey, supported contracts, and unsupported workflows. Future abstractions could include datasets as versioned assets, transformations as reusable definitions, and ownership/access policies; do not build these without a user scenario.

**Acceptance tests:**
- A new user can reproduce one complete upload -> process -> query -> save -> download flow from docs.
- README distinguishes implemented API self-service from deferred enterprise capabilities.
- A clearly defined dataset lifecycle and naming policy is documented.

### F7 — Operational boundaries and deployment labs (LOW for MVP; important communication)

**Documented:** Compose runs complete local stack; Terraform/Kubernetes are separate API-only labs. Ports bind to 127.0.0.1; no authentication; volumes persist but are not backups; migrations are manual for existing volumes. Session 023 reported Terraform API lab verification, not a fresh full-stack validation.

**Recommendation:** Do not present labs as full platform deployments. Explain startup, migrations, dependency failures, data retention, and what a backup/restore would need to cover. Do not expose this SQL API to untrusted users without a dedicated security review.

## 5. Prioritized implementation plan

### Phase A — Reliability first (recommended next milestone)

1. **Baseline:** Inspect code paths and rerun tests; record current commit SHA, tests, and smoke-test output. No behavior changes.
2. **Crash recovery design:** Document run-state transition graph, lease/claim ownership model, retry policy, and stale-worker fencing.
3. **Implement and test crash recovery:** Fault injection at claim, during transform, after MinIO upload, and before final DB commit.
4. **Dual-write design:** Compare transactional outbox vs reconciler/republisher; choose based on MVP scope.
5. **Implement and test chosen publication recovery.**

### Phase B — Resource and artifact correctness

6. Add query concurrency admission limits and overload tests.
7. Make saved-table retries predictable (idempotency semantics).
8. Add object reconciliation/integrity checks; decide how orphan cleanup is authorized.

### Phase C — Portfolio presentation

9. Add 2–3 ADRs: RabbitMQ vs PostgreSQL queue, DuckDB vs Spark, PostgreSQL metadata + MinIO objects.
10. Add a failure-mode matrix and concise self-service user journey to docs.
11. Verify clean-clone setup, migrations, tests, and full Compose smoke test; label separate labs accurately.

**Do not implement as MVP blockers:** Kafka/event streaming, Spark, enterprise IAM, multi-tenancy, Kubernetes autoscaling, full HA, distributed tracing, complex governance, cross-table SQL federation, or a web UI. Add only when tied to a clear user requirement.

## 6. Failure-mode test matrix

| Injection | Expected property | Current confidence |
|---|---|---|
| Duplicate RabbitMQ delivery after terminal run | No repeated committed effect | Documented behavior; verify in tests |
| Worker stops before claim | Queued work survives and can be processed later | Documented verified behavior |
| Worker stops after claim | Recoverable or explicitly failed; never silently stuck | Known gap |
| Broker unavailable during submission | Durable recoverable intent or explicit reconciliation | Known gap |
| Publisher confirmation lost | Safe duplicate publish/retry | Needs stronger recovery design |
| MinIO upload succeeds, DB commit fails | No invisible permanent inconsistency | Known gap |
| Ten simultaneous SQL requests | Bounded total execution/resource demand | Known gap |
| Source object deleted externally | Controlled error + integrity audit | Verify implementation |
| API/worker restart | Persistent metadata and artifacts remain usable | Verify full workflow |
| Existing DB volume with schema changes | Explicit migration, no accidental re-init | Manual migration documented |

## 7. Ten interview questions and defensible answers

1. **Why RabbitMQ rather than a PostgreSQL job queue?** Dedicated messaging, delivery and acknowledgments; PostgreSQL `SKIP LOCKED` could be simpler at this scale. RabbitMQ chosen to explore async messaging; introduces dual-write.
2. **What happens if a worker dies after claiming a run?** Current documented gap: run can remain `running`. Design leases, attempts, fencing, recovery and retry limits.
3. **What if DB commit succeeds but RabbitMQ publish fails?** Run may be stranded queued. Publisher confirms don't make DB and broker atomic. Outbox or reconciler is required.
4. **Why PostgreSQL + MinIO instead of storing files in PostgreSQL?** Transactional relational metadata vs independent binary artifacts; accept cross-system consistency burden.
5. **Do you guarantee exactly-once processing?** No. Broker redelivery can duplicate; conditional claims cover some duplicates, not all side effects or repeated client submissions.
6. **Why DuckDB instead of Spark/Pandas/PostgreSQL SQL?** Efficient embedded analytical SQL and Parquet for bounded single-node workloads; Spark is unnecessary overhead at this scale.
7. **What protects the API from 100 concurrent SQL requests?** Currently no global admission limit; add semaphore/overload policy and consider isolation if multi-instance.
8. **What if MinIO writes Parquet but metadata commit fails?** Orphan/uncertain result; use unique keys, staged lifecycle, idempotency, reconciliation.
9. **Why call it self-service rather than ETL?** API enables independent dataset registration, processing, query, save and download; acknowledge missing organizational platform capabilities.
10. **Why Terraform and Kubernetes if Compose runs everything?** Separate API-only infrastructure learning labs, not complete pipeline deployments; describe them precisely.

## 8. Suggested prompt for Codex / another AI agent

> Read `docs/ARCHITECTURE_REVIEW.md`, the current README, queue behavior notes, DB schema, and relevant source/tests. Treat the review as advisory, not authoritative code documentation. First verify the current behavior and report discrepancies. Focus ONLY on **F1: worker crash recovery**. Before changing files, propose the smallest design consistent with the existing architecture, identify state transitions, race conditions, and failure-injection tests, and explain how stale workers are fenced. Do not add Kafka, Spark, Kubernetes, or unrelated features. Wait for my approval before implementing. After approval, make incremental changes, run relevant tests, and summarize evidence and remaining limitations.

## 9. Definition of done for each roadmap task

- The actual failure mode is reproduced or convincingly demonstrated with a focused test.
- The chosen invariant/guarantee is written down and can be explained in plain English.
- The change is minimal and avoids unrelated infrastructure.
- Automated tests cover success, failure, duplicate/retry, and relevant concurrency edges.
- Existing API behavior is preserved or intentional changes are documented.
- Documentation describes **what is implemented**, **what is still missing**, and **how to verify**.
- The human owner approves the design before implementation and reviews the result.

---

**Review boundaries:** This document transforms the architecture-review conversation into an actionable roadmap; it is not a verbatim transcript. It includes both documented observations and explicitly labeled recommendations. No repository files were modified as part of the review or this export.
