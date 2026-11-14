# Local platform decisions

These choices fit a single-machine learning prototype; they do not claim public-service readiness.

- **PostgreSQL owns metadata and run state.** Conditional updates make a claim atomic and allow token-guarded finalization. A migration is required for existing volumes, and database backups remain out of scope.
- **MinIO holds CSV and Parquet bytes.** Database rows store object keys rather than file contents. Attempt-specific Parquet paths protect new output from stale workers, while the read-only inventory exposes missing and unreferenced objects for review.
- **RabbitMQ carries work requests.** The transactional outbox records intent in PostgreSQL before publication. Publisher confirms and a reconciler close the lost-message window; duplicate delivery is expected and handled through database claims.
- **DuckDB processes and queries files locally.** It keeps the transformation compact and supports bounded SQL previews and exports. A process-local admission limit controls simultaneous queries in one API instance; it is not hard isolation for untrusted users.
