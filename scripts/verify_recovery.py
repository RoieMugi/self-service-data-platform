"""Exercise R06/R07 failure recovery on a disposable GitHub Actions stack.

This script stops Compose services and changes run state. It is intentionally
restricted to GitHub Actions; never use it against a retained local stack.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
from minio import Minio
from psycopg.rows import dict_row


def require_disposable_ci():
    if os.getenv("GITHUB_ACTIONS") != "true" or os.getenv("ALLOW_DISPOSABLE_FAULTS") != "1":
        raise RuntimeError("Recovery verification requires an explicitly enabled GitHub Actions stack")


def compose(*args):
    subprocess.run(["docker", "compose", *args], check=True)


def config():
    return dict(
        line.split("=", 1)
        for line in Path(".env").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )


def wait_for(description, probe, timeout=90):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = probe()
            if last:
                return last
        except (httpx.RequestError, psycopg.OperationalError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {description}; last result: {last!r}")


def post(client, path, **kwargs):
    response = client.post(path, **kwargs)
    if response.is_error:
        raise RuntimeError(f"POST {path} returned {response.status_code}: {response.text}")
    return response.json()


def make_upload(client, label):
    dataset = post(client, "/datasets", json={"name": f"recovery-{label}-{uuid4().hex[:8]}"})
    upload = post(
        client,
        f"/datasets/{dataset['id']}/uploads",
        files={"file": ("sales.csv", b"region,amount\nnorth,10\nsouth,5\n", "text/csv")},
    )
    return upload["id"]


def run_row(db, run_id):
    with db.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """SELECT r.status, r.attempt_count, r.claim_token, r.curated_object_key,
                      o.published_at FROM processing_runs r
                      JOIN processing_outbox o ON o.run_id = r.id WHERE r.id = %s""",
            (run_id,),
        )
        return cursor.fetchone()


def run_with_status(db, run_id, status):
    row = run_row(db, run_id)
    return row if row["status"] == status else None


def expire_claim(db, run_id, attempts):
    token = uuid4()
    with db.transaction():
        with db.cursor() as cursor:
            cursor.execute(
                """UPDATE processing_runs SET status = 'running',
                      started_at = CURRENT_TIMESTAMP - INTERVAL '10 minutes',
                      attempt_count = %s, claim_token = %s,
                      lease_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                      WHERE id = %s AND status = 'queued' RETURNING id""",
                (attempts, token, run_id),
            )
            assert cursor.fetchone() is not None, "Run was not queued before crash injection"
    return token


def reset_outbox(db, run_id):
    with db.transaction():
        with db.cursor() as cursor:
            cursor.execute(
                "UPDATE processing_outbox SET published_at = NULL WHERE run_id = %s",
                (run_id,),
            )


def install_finalization_hold(db):
    with db.transaction():
        with db.cursor() as cursor:
            cursor.execute("""CREATE FUNCTION ci_hold_processing_success() RETURNS trigger AS $$
                BEGIN PERFORM pg_sleep(20); RETURN NEW; END;
                $$ LANGUAGE plpgsql""")
            cursor.execute("""CREATE TRIGGER ci_hold_processing_success
                BEFORE UPDATE OF status ON processing_runs
                FOR EACH ROW WHEN (NEW.status = 'succeeded')
                EXECUTE FUNCTION ci_hold_processing_success()""")


def remove_finalization_hold(db):
    with db.transaction():
        with db.cursor() as cursor:
            cursor.execute("DROP TRIGGER IF EXISTS ci_hold_processing_success ON processing_runs")
            cursor.execute("DROP FUNCTION IF EXISTS ci_hold_processing_success()")


def worker_in_finalization_hold(db):
    with db.cursor() as cursor:
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE wait_event = 'PgSleep')")
        return cursor.fetchone()[0]


def force_expire_running(db, run_id):
    with db.transaction():
        with db.cursor() as cursor:
            cursor.execute("""UPDATE processing_runs
                SET lease_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                WHERE id = %s AND status = 'running' RETURNING id""", (run_id,))
            assert cursor.fetchone() is not None, "Killed worker did not leave a running row"


def verify_submission_rollback(db, upload_id):
    run_id = uuid4()
    try:
        with db.transaction():
            with db.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO processing_runs (id, upload_id, status) VALUES (%s, %s, 'queued')",
                    (run_id, upload_id),
                )
                cursor.execute(
                    "INSERT INTO processing_outbox (run_id, correlation_id) VALUES (%s, %s)",
                    (run_id, uuid4()),
                )
                raise RuntimeError("Deliberate submission rollback")
    except RuntimeError as exc:
        assert str(exc) == "Deliberate submission rollback"
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM processing_runs WHERE id = %s", (run_id,))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM processing_outbox WHERE run_id = %s", (run_id,))
        assert cursor.fetchone()[0] == 0


def main():
    require_disposable_ci()
    settings = config()
    database_url = (
        f"postgresql://{settings['POSTGRES_USER']}:{settings['POSTGRES_PASSWORD']}"
        f"@127.0.0.1:5432/{settings['POSTGRES_DB']}"
    )
    broker_url = "http://127.0.0.1:15672"
    broker_auth = (settings["RABBITMQ_DEFAULT_USER"], settings["RABBITMQ_DEFAULT_PASS"])
    worker_running = True
    broker_running = True
    delay_trigger_installed = False

    with psycopg.connect(database_url, autocommit=True) as db, httpx.Client(
        base_url="http://127.0.0.1:8000", timeout=20
    ) as client, httpx.Client(base_url=broker_url, auth=broker_auth, timeout=5) as broker:
        def broker_ready():
            return broker.get("/api/overview").status_code == 200

        def queue_depth():
            response = broker.get("/api/queues/%2F/processing_runs")
            response.raise_for_status()
            return response.json()["messages_ready"]

        def purge_queue():
            response = broker.delete("/api/queues/%2F/processing_runs/contents")
            response.raise_for_status()

        try:
            wait_for("API readiness", lambda: client.get("/db-health").status_code == 200)
            wait_for("RabbitMQ readiness", broker_ready)

            # R06: a worker vanished after claiming attempt 1. The reconciler
            # must requeue it, and a fresh worker must finish attempt 2.
            compose("stop", "worker")
            worker_running = False
            upload_id = make_upload(client, "expired")
            recovered_id = UUID(post(client, f"/uploads/{upload_id}/process")["run_id"])
            assert run_row(db, recovered_id)["published_at"] is not None
            purge_queue()  # The vanished worker's original delivery is gone.
            old_token = expire_claim(db, recovered_id, 1)
            wait_for(
                "expired attempt to be requeued and republished",
                lambda: (row := run_row(db, recovered_id))["status"] == "queued"
                and row["published_at"] is not None and row["claim_token"] is None,
            )
            compose("start", "worker")
            worker_running = True
            recovered = wait_for(
                "retried run to succeed",
                lambda: run_with_status(db, recovered_id, "succeeded"),
            )
            assert recovered["attempt_count"] == 2, recovered
            assert "/attempt-2/" in recovered["curated_object_key"], recovered
            assert recovered["claim_token"] is None
            assert old_token != recovered["claim_token"]

            # R06: hold finalization inside PostgreSQL after the artifact has
            # been uploaded, kill the actual worker, and recover the run.
            install_finalization_hold(db)
            delay_trigger_installed = True
            upload_id = make_upload(client, "killed")
            killed_id = UUID(post(client, f"/uploads/{upload_id}/process")["run_id"])
            wait_for("worker to reach finalization hold", lambda: worker_in_finalization_hold(db))
            compose("kill", "worker")
            compose("stop", "worker")
            worker_running = False
            remove_finalization_hold(db)
            delay_trigger_installed = False
            interrupted = run_row(db, killed_id)
            assert interrupted["status"] == "running" and interrupted["attempt_count"] == 1, interrupted
            force_expire_running(db, killed_id)
            os.environ["DATABASE_URL"] = database_url
            from app.main import ACTIVE_CLAIM_TOKEN, complete_processing_run
            context = ACTIVE_CLAIM_TOKEN.set(interrupted["claim_token"])
            try:
                assert complete_processing_run(killed_id, 1, "stale/should-not-publish.parquet") is None
            finally:
                ACTIVE_CLAIM_TOKEN.reset(context)
            assert run_row(db, killed_id)["curated_object_key"] is None
            wait_for("killed run to be requeued", lambda: run_with_status(db, killed_id, "queued"))
            compose("start", "worker")
            worker_running = True
            killed = wait_for(
                "killed run to succeed on retry",
                lambda: run_with_status(db, killed_id, "succeeded"),
            )
            assert killed["attempt_count"] == 2 and "/attempt-2/" in killed["curated_object_key"], killed
            storage = Minio(
                "127.0.0.1:9000", access_key=settings["MINIO_ROOT_USER"],
                secret_key=settings["MINIO_ROOT_PASSWORD"], secure=False,
            )
            key_prefix = killed["curated_object_key"].split("attempt-2/")[0]
            assert list(storage.list_objects("curated", prefix=key_prefix + "attempt-1/"))
            assert list(storage.list_objects("curated", prefix=key_prefix + "attempt-2/"))

            # R06: an exhausted third attempt becomes terminal instead of
            # cycling indefinitely.
            compose("stop", "worker")
            worker_running = False
            upload_id = make_upload(client, "exhausted")
            exhausted_id = UUID(post(client, f"/uploads/{upload_id}/process")["run_id"])
            purge_queue()
            expire_claim(db, exhausted_id, 3)
            exhausted = wait_for(
                "attempt budget to fail",
                lambda: run_with_status(db, exhausted_id, "failed"),
            )
            assert exhausted["attempt_count"] == 3, exhausted

            # R07: submission commits while the broker is offline. The
            # reconciler publishes the pending intent after broker recovery.
            verify_submission_rollback(db, upload_id)
            compose("stop", "rabbitmq")
            broker_running = False
            upload_id = make_upload(client, "broker")
            outage_id = UUID(post(client, f"/uploads/{upload_id}/process")["run_id"])
            pending = run_row(db, outage_id)
            assert pending["status"] == "queued" and pending["published_at"] is None, pending
            compose("start", "rabbitmq")
            broker_running = True
            wait_for("RabbitMQ restart", broker_ready)
            wait_for("pending publication", lambda: run_row(db, outage_id)["published_at"] is not None)
            compose("start", "worker")
            worker_running = True
            delivered = wait_for(
                "outage run to succeed",
                lambda: run_with_status(db, outage_id, "succeeded"),
            )
            assert delivered["attempt_count"] == 1, delivered

            # R07: a lost database confirmation after broker acceptance
            # republishes the same run. Only one delivery may claim it.
            compose("stop", "worker")
            worker_running = False
            upload_id = make_upload(client, "duplicate")
            duplicate_id = UUID(post(client, f"/uploads/{upload_id}/process")["run_id"])
            assert run_row(db, duplicate_id)["published_at"] is not None
            wait_for("first queued message", lambda: queue_depth() >= 1)
            reset_outbox(db, duplicate_id)
            wait_for("repeated publication", lambda: queue_depth() >= 2)
            assert run_row(db, duplicate_id)["published_at"] is not None
            compose("start", "worker")
            worker_running = True
            duplicate = wait_for(
                "duplicate-delivery run to succeed",
                lambda: run_with_status(db, duplicate_id, "succeeded"),
            )
            wait_for("duplicate deliveries to clear", lambda: queue_depth() == 0)
            assert run_row(db, duplicate_id)["attempt_count"] == 1, duplicate

            print(json.dumps({
                "status": "passed",
                "expired_run": str(recovered_id),
                "killed_worker_run": str(killed_id),
                "exhausted_run": str(exhausted_id),
                "broker_outage_run": str(outage_id),
                "duplicate_delivery_run": str(duplicate_id),
            }, indent=2))
        finally:
            if delay_trigger_installed:
                remove_finalization_hold(db)
            if not broker_running:
                compose("start", "rabbitmq")
            if not worker_running:
                compose("start", "worker")


if __name__ == "__main__":
    main()
