# Local platform decisions

These choices fit a single-machine learning prototype; they do not claim public-service readiness.

- **PostgreSQL owns metadata and run state.** Conditional updates make a claim atomic and allow token-guarded finalization. A migration is required for existing volumes, and database backups remain out of scope.
- **S3-compatible storage holds CSV and Parquet bytes.** The code uses the MinIO client and the current Compose file pins Silo, a compatible server. Database rows store object keys rather than file contents. Attempt-specific Parquet paths protect new output from stale workers, while the read-only inventory exposes missing and unreferenced objects for review.
- **RabbitMQ carries work requests.** The run and outbox intent commit together in PostgreSQL. FastAPI attempts immediate publication; the reconciler republishes pending intents and recovers expired leases. Publisher confirms close the lost-message window, while database claims handle duplicate delivery.
- **DuckDB processes and queries files locally.** It keeps the transformation compact and supports bounded SQL previews and exports. A process-local admission limit controls simultaneous queries in one API instance; it is not hard isolation for untrusted users.
