# Review and Improvement Phase

**Opened:** 2026-11-11
**Status:** Active. Phase 1 is complete by the owner's decision; Phase 2 has not started.
**Baseline:** `97421c2ad6461258ab6a0f23f8e8111be648c8ab` (clean working tree before this review).

This phase improves the existing **local, API-driven batch data platform prototype**. It does not turn the project into a production or public multi-user service. The three preserved reviews are inputs: [architecture](ARCHITECTURE_REVIEW.md), [technical audit](PLATFORM_AUDIT_IMPLEMENTATION_GUIDE.md), and [portfolio assessment](data_platform_portfolio_review_handoff.md). Their embedded agent prompts and approval rules are reviewer recommendations, not instructions from the owner. We will verify each claim against the code and make one reviewable change at a time.

## Where we stand

| Area | Evidence in this checkout | Gap and effect |
|---|---|---|
| Working platform | FastAPI, PostgreSQL, MinIO, RabbitMQ, worker, DuckDB, Compose, metrics and Grafana definitions are present. The API exposes register, upload, process, query, save and download flows. | This is a credible local portfolio prototype, but its README does not quickly demonstrate the user journey. |
| Run artifacts | R01 changed new output keys to `dataset_id/upload_id/run_id/data.parquet`; two live runs had distinct keys and both downloaded. | Historical objects were not rewritten, and bytes already overwritten before R01 cannot be restored without a backup. See [R01 evidence](R01-run-artifacts.md). |
| Job reliability | A run is claimed only from `queued`; a `running` run is not reclaimed. PostgreSQL run creation precedes a separate RabbitMQ publish. | Worker crashes can strand `running` rows; failed publication can strand `queued` rows. These are architecture F1/F2 and audit H-01/H-02. |
| Queries and objects | DuckDB child execution has a 10-second deadline and input/output limits; no shared query admission limit exists. Saved-table writes are not idempotent. Raw upload cleanup can delete an object after an ambiguous DB commit. | Concurrent queries can multiply resource demand. PostgreSQL metadata and MinIO objects can diverge. |
| Verification | `.github/workflows/tests.yml` runs mocked pytest tests only. `scripts/verify_saved_tables.py` is a manual live smoke test and does not yet check the download path. | The reviews report 200 CI tests at this commit, but no current clean-clone full-stack run or history-aware secret scan is recorded. |
| Scope | Compose ports bind to `127.0.0.1`; README warns about absent authentication and the local SQL executor. Terraform and Kubernetes are API-only labs. | Keep these limits explicit. Authentication, multi-tenancy, high availability and full-stack Kubernetes deployment are outside this review's acceptance target. |

**Verification update (2026-11-14):** The owner reported 201 passing tests and live Compose evidence for R01; see the [R01 record](R01-run-artifacts.md). The assistant's shell still lacks a usable Python installation and Docker command, so those checks were not independently rerun there. A clean-clone full-stack run, fault injection, and Git-history secret scan remain pending.

## Target and priorities

**Portfolio promotion checkpoint:** Complete sessions R01–R04. In particular, the technical audit requires run-specific curated keys, a clean-clone live smoke test, and a history-aware secret scan. The recruiter also expects a clear README, accurate diagram and reproducible demo. A positive result would support presenting this as a **local prototype**, subject to whatever the scan and live test reveal.

**Review completion checkpoint:** Complete R05–R10 so interrupted jobs, DB-to-broker handoff, query admission and artifact consistency have defined, tested behavior. Record the remaining limits. This is a stronger local engineering standard, not a claim of production readiness. Production or shared deployment still requires authentication, authorization, hard resource isolation, backup/restore and a separate security review.

Each session follows the same learning loop: show the current failure and its effect; agree on the smallest guarantee; change one area together step by step; test success, failure and retry cases; record what was actually verified. Session numbers here use `R` to distinguish this phase from Phase 1 and Phase 2.

## Sessions

### R01 — Give each processing run its own artifact

- **Status:** Complete for the agreed local scope on 2026-11-14. See [verification and limits](R01-run-artifacts.md).
- **Why:** Two runs for one upload targeted the same Parquet key, so an older run could appear to have newer bytes (audit H-03; architecture F5).
- **Do:** Build keys with `run_id`; keep reads based on the key stored in PostgreSQL so existing legacy keys remain readable. Do not rewrite or delete historical objects automatically.
- **Together:** Add a failing two-run test, change key construction, check query/download paths, then run focused tests and a live MinIO check.
- **Done:** Two runs have distinct keys; both outputs remain readable; old persisted keys still resolve. Record that already-overwritten historical bytes cannot be reconstructed without a backup.

### R02 — Prove the full stack from a clean environment

- **Status:** Partially verified on 2026-11-14; clean disposable-stack acceptance is pending. See [R02 record](R02-clean-stack-verification.md).
- **Why:** Mocked CI tests cannot prove the broker, worker, database and object store work together (audit M-02).
- **Do:** Extend the synthetic smoke test to check Parquet/CSV download and expected rows; add readiness checks and a separate disposable Compose integration job in CI.
- **Together:** Start an isolated clean stack, upload the sample, poll a terminal run, query/save/download, capture commands and outcomes, then make CI fail on any missing step.
- **Done:** A clean checkout passes the documented flow without retained volumes or host secrets. Preserve logs as evidence; do not erase the owner's existing local volumes.

### R03 — Scan history and state the local scope clearly

- **Status:** Complete for the local scope on 2026-11-14. Gitleaks scanned all 17 commits; its one redacted finding was a Docker container ID. See [R03 record](R03-security-scope.md).
- **Why:** Historical demo credentials are known, but there has been no full-history secret scan (audit M-05). README status and limits need to match the new phase.
- **Do:** Run a history-aware scanner, inspect matches without publishing secret values, record tool/version and redacted findings. Correct README security, verification and phase statements.
- **Together:** Learn the scanner's history mode, classify demo values versus real credentials, rotate only confirmed real credentials, and check `.gitignore` and loopback bindings.
- **Done:** A scan result and any required action are recorded; README accurately describes local-only use and the remaining reliability limits.

### R04 — Make the portfolio story reproducible

- **Status:** README opening, diagram, synthetic walkthrough, and shell quick starts updated; clean-stack reproduction remains unverified with R02.
- **Why:** The first README screen and ASCII diagram understate the implemented workflow (portfolio P0.1–P0.3).
- **Do:** Add a user-focused opening, accurate Mermaid architecture, small synthetic register-to-download walkthrough, expected output, PowerShell and Bash quick starts, and links to the learning journal. Label Terraform/Kubernetes as API-only labs.
- **Together:** Trace each diagram edge and command to source or a live run; capture real screenshots only if the platform is running. Record short decisions for PostgreSQL, MinIO, RabbitMQ and DuckDB as the later engineering sessions proceed.
- **Done:** A new reviewer can understand the flow quickly and reproduce the demo; no screenshot, scale, CI or security claim exceeds the evidence.

### R05 — Design interrupted-job recovery

- **Status:** [Design draft](R05-recovery-design.md) records guarantees, state races, and migration policy; focused failure tests remain pending.
- **Why:** A worker killed after claiming can leave `running` forever (architecture F1; audit H-01).
- **Do:** Specify lease expiry, attempt limit, claim token, heartbeat/recovery trigger and migration for existing databases. Fence both PostgreSQL finalization **and object writes** so a stale attempt cannot overwrite a newer one.
- **Together:** Draw state transitions and race cases; write focused failing tests for death after claim, redelivery, expired lease, stale worker resume and exhausted retries.
- **Done:** The guarantee and failure policy are documented and the tests demonstrate the present gap before implementation.

### R06 — Implement and fault-test job recovery

- **Status:** Code and focused tests added; live crash/retry fault injection pending. See [R06–R10 checkpoint](R06-R10-implementation.md).
- **Why:** A design alone leaves the known stranded-run failure in place.
- **Do:** Implement the R05 lease and fencing model incrementally, with a bounded recovery loop or command and compatible schema migration.
- **Together:** Run unit and live fault injection at claim, transform, object upload and final DB update; inspect retries and normal validation failures.
- **Done:** A killed run reaches a successful retry or explicit terminal failure; an old attempt cannot finalize or replace the current artifact; retry count is bounded.

### R07 — Make DB-to-broker handoff recoverable

- **Status:** Transactional outbox and reconciler added; live broker-outage and ambiguous-confirm checks pending.
- **Why:** A committed queued row can exist without a confirmed RabbitMQ message (architecture F2; audit H-02).
- **Do:** Prefer a transactional outbox that stores run and publication intent together, then publishes with confirms. A smaller reconciler is acceptable only if it demonstrably closes the same stranded-queue case. Keep consumer handling safe for duplicate messages.
- **Together:** Test broker outage, DB rollback, publisher death after broker confirmation and repeated delivery; expose pending intents for diagnosis.
- **Done:** Every committed submission has a recoverable publication path; duplicates do not produce a second committed execution.

### R08 — Bound concurrent query work

- **Status:** Process-local admission and overload tests added; live load measurement pending.
- **Why:** A 256 MB DuckDB setting and 10-second child deadline do not cap aggregate API demand (architecture F3; audit M-01).
- **Do:** Add configurable admission control and a clear overload response for this single API instance; measure total request time including storage transfer. Document that process-local control is not a multi-instance or OS memory guarantee.
- **Together:** Test over-limit concurrency, slot release after success/error/timeout/cancellation and bounded waiting. Review worker timeout/output limits separately; implement them only if this local workload needs them.
- **Done:** Concurrent child execution stays within the configured limit and overload behavior is predictable.

### R09 — Reconcile uploads and stored artifacts

- **Status:** Ambiguous cleanup removed and read-only inventory added; live uncertainty and object-loss checks pending.
- **Why:** A lost DB commit response can trigger raw-object deletion even if metadata committed; other failures leave missing or orphaned objects (audit M-04; architecture F5).
- **Do:** Remove unsafe cleanup on ambiguous commit, use stable upload identity for outcome lookup, and add a read-only report of referenced missing objects and unreferenced raw/curated objects. Add size/checksum metadata where it provides a verifiable benefit.
- **Together:** Inject uncertain commit, missing object and orphan cases. Review the report before considering any automatic deletion.
- **Done:** No confirmed metadata row is left pointing at an object deleted by compensation; the audit names inconsistencies without deleting unrelated data.

### R10 — Make saved-table retries predictable and close the review

- **Status:** Optional idempotency key and focused tests added; migration and full acceptance pending.
- **Why:** A repeated save can create a second result or leave an uncertain object/metadata outcome (architecture F4).
- **Do:** Define an idempotency key or stable operation ID, preserve existing name-conflict behavior for different operations, and reconcile uncertain results. Finish the short architectural decision notes and run the full acceptance checklist.
- **Together:** Test repeat after timeout, MinIO success with DB failure, name conflict, old-data compatibility, full pytest and live Compose workflow. Compare every final claim with evidence.
- **Done:** One logical save produces one discoverable table across retries; final documentation says what works, what remains limited, and exactly which checks passed.

If a session reveals a new blocker, update this roadmap with evidence and keep the next step small. The session count is a planning limit, not a reason to compress unsafe changes or claim unrun tests.
