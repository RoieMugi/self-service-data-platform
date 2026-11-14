"""Verify R08-R10 against a disposable GitHub Actions stack.

This injects database locks, missing objects, and uncertain commit results.
It requires explicit CI authorization so it cannot alter a retained stack.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import psycopg
from fastapi.testclient import TestClient
from minio import Minio

from scripts.verify_recovery import config, make_upload, post, require_disposable_ci, wait_for


SOURCE_CSV = b"region,amount\nnorth,10\nsouth,5\n"
QUERY = {"sql": "SELECT COUNT(*) AS total FROM dataset"}
SAVE_SQL = "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region ORDER BY region"


def db_value(db, statement, values=()):
    with db.cursor() as cursor:
        cursor.execute(statement, values)
        row = cursor.fetchone()
        return row[0] if row else None


def read_object(storage, bucket, key):
    response = storage.get_object(bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def put_object(storage, bucket, key, content, content_type="application/octet-stream"):
    storage.put_object(bucket, key, BytesIO(content), len(content), content_type=content_type)


def timed_query(run_id):
    start = time.monotonic()
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
        response = client.post(f"/processing-runs/{run_id}/query", json=QUERY)
    return response, time.monotonic() - start


def blocked_query_count(db):
    return db_value(
        db,
        """SELECT COUNT(*) FROM pg_stat_activity
           WHERE wait_event_type = 'Lock'
             AND query LIKE '%FROM processing_runs%'
             AND query LIKE '%WHERE id =%'
             AND pid <> pg_backend_pid()""",
    )


def verify_query_admission(db, client, run_id):
    with ThreadPoolExecutor(max_workers=2) as pool:
        with db.transaction():
            with db.cursor() as cursor:
                cursor.execute("LOCK TABLE processing_runs IN ACCESS EXCLUSIVE MODE")
            futures = [pool.submit(timed_query, run_id) for _ in range(2)]
            wait_for("two occupied query slots", lambda: blocked_query_count(db) >= 2, timeout=15)
            start = time.monotonic()
            overload = client.post(f"/processing-runs/{run_id}/query", json=QUERY)
            overload_seconds = time.monotonic() - start
            assert overload.status_code == 429, (overload.status_code, overload.text)
        completed = [future.result(timeout=30) for future in futures]
    assert all(response.status_code == 200 for response, _ in completed), completed
    assert all(response.json()["rows"] == [[2]] for response, _ in completed)
    invalid = client.post(
        f"/processing-runs/{run_id}/query", json={"sql": "DROP TABLE dataset"}
    )
    assert invalid.status_code == 422, (invalid.status_code, invalid.text)
    released = client.post(f"/processing-runs/{run_id}/query", json=QUERY)
    assert released.status_code == 200 and released.json()["rows"] == [[2]]
    return {
        "busy_responses": 1,
        "overload_seconds": round(overload_seconds, 3),
        "successful_query_seconds": [round(seconds, 3) for _, seconds in completed],
    }


def verify_upload_uncertainty(db, client, injected_api, storage):
    dataset = post(client, "/datasets", json={"name": f"uncertain-upload-{uuid4().hex[:8]}"})
    from app import main as api

    original_insert = api.insert_upload

    def committed_then_lost(*args, **kwargs):
        original_insert(*args, **kwargs)
        raise RuntimeError("Injected loss of upload commit reply")

    with patch.object(api, "insert_upload", side_effect=committed_then_lost):
        response = injected_api.post(
            f"/datasets/{dataset['id']}/uploads",
            files={"file": ("sales.csv", SOURCE_CSV, "text/csv")},
        )
    assert response.status_code == 500, (response.status_code, response.text)
    upload_id = UUID(response.json()["detail"]["upload_id"])
    metadata = client.get(f"/uploads/{upload_id}")
    assert metadata.status_code == 200, (metadata.status_code, metadata.text)
    raw_key = metadata.json()["object_key"]
    assert read_object(storage, "raw", raw_key) == SOURCE_CSV
    download = client.get(f"/uploads/{upload_id}/download")
    assert download.status_code == 200 and download.content == SOURCE_CSV
    assert db_value(db, "SELECT COUNT(*) FROM uploads WHERE id = %s", (upload_id,)) == 1
    return upload_id, raw_key


def verify_object_inventory(storage, audit, raw_key, curated_key):
    raw_bytes = read_object(storage, "raw", raw_key)
    curated_bytes = read_object(storage, "curated", curated_key)
    raw_orphan = f"ci-orphan-{uuid4().hex}.csv"
    curated_orphan = f"ci-orphan-{uuid4().hex}.parquet"
    put_object(storage, "raw", raw_orphan, SOURCE_CSV, "text/csv")
    put_object(storage, "curated", curated_orphan, curated_bytes)
    storage.remove_object("raw", raw_key)
    storage.remove_object("curated", curated_key)
    try:
        report = audit.inventory()
        assert raw_key in report["raw"]["referenced_missing"], report
        assert curated_key in report["curated"]["referenced_missing"], report
        assert raw_orphan in report["raw"]["unreferenced_stored"], report
        assert curated_orphan in report["curated"]["unreferenced_stored"], report
        # Auditing twice must not delete the intentionally orphaned objects.
        assert audit.inventory() == report
        storage.stat_object("raw", raw_orphan)
        storage.stat_object("curated", curated_orphan)
    finally:
        put_object(storage, "raw", raw_key, raw_bytes, "text/csv")
        put_object(storage, "curated", curated_key, curated_bytes)
        storage.remove_object("raw", raw_orphan)
        storage.remove_object("curated", curated_orphan)
    clean = audit.inventory()
    assert raw_key not in clean["raw"]["referenced_missing"], clean
    assert curated_key not in clean["curated"]["referenced_missing"], clean
    return {"missing_raw_detected": True, "missing_curated_detected": True}


def verify_saved_table_retries(db, client, injected_api, storage, audit, run_id):
    from app import main as api

    name = f"retry-{uuid4().hex[:8]}"
    request = {"name": name, "sql": SAVE_SQL}
    key = uuid4()
    original_insert = api.insert_saved_table

    def committed_then_lost(*args, **kwargs):
        original_insert(*args, **kwargs)
        raise RuntimeError("Injected loss of table commit reply")

    with patch.object(api, "insert_saved_table", side_effect=committed_then_lost):
        response = injected_api.post(
            f"/processing-runs/{run_id}/tables",
            json=request,
            headers={"Idempotency-Key": str(key)},
        )
    assert response.status_code == 201, (response.status_code, response.text)
    table = response.json()
    retry = client.post(
        f"/processing-runs/{run_id}/tables",
        json=request,
        headers={"Idempotency-Key": str(key)},
    )
    assert retry.status_code == 201 and retry.json()["id"] == table["id"], retry.text
    assert db_value(db, "SELECT COUNT(*) FROM saved_tables WHERE operation_id = %s", (key,)) == 1
    assert client.get(f"/tables/{table['id']}/download").status_code == 200
    changed = client.post(
        f"/processing-runs/{run_id}/tables",
        json={"name": name, "sql": "SELECT * FROM dataset"},
        headers={"Idempotency-Key": str(key)},
    )
    assert changed.status_code == 409, (changed.status_code, changed.text)
    before_conflict = {
        item.object_name for item in storage.list_objects("curated", prefix="tables/", recursive=True)
    }
    conflict = client.post(
        f"/processing-runs/{run_id}/tables",
        json=request,
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert conflict.status_code == 409, (conflict.status_code, conflict.text)
    after_conflict = {
        item.object_name for item in storage.list_objects("curated", prefix="tables/", recursive=True)
    }
    assert after_conflict == before_conflict, "Name conflict left an unregistered object"

    # The object write succeeds, but the database insert does not commit.
    # Keep that uncertain object for audit, then retry the logical save.
    key2 = uuid4()
    request2 = {"name": f"retry-after-failure-{uuid4().hex[:8]}", "sql": SAVE_SQL}
    with patch.object(api, "insert_saved_table", side_effect=RuntimeError("Injected DB failure")):
        failed = injected_api.post(
            f"/processing-runs/{run_id}/tables",
            json=request2,
            headers={"Idempotency-Key": str(key2)},
        )
    assert failed.status_code == 503, (failed.status_code, failed.text)
    failed_table_id = UUID(failed.json()["detail"]["table_id"])
    orphan_key = f"tables/{failed_table_id}/data.parquet"
    storage.stat_object("curated", orphan_key)
    assert client.get(f"/tables/{failed_table_id}").status_code == 404
    retry2 = client.post(
        f"/processing-runs/{run_id}/tables",
        json=request2,
        headers={"Idempotency-Key": str(key2)},
    )
    assert retry2.status_code == 201, (retry2.status_code, retry2.text)
    assert retry2.json()["id"] != str(failed_table_id)
    assert db_value(db, "SELECT COUNT(*) FROM saved_tables WHERE operation_id = %s", (key2,)) == 1
    assert orphan_key in audit.inventory()["curated"]["unreferenced_stored"]
    storage.stat_object("curated", orphan_key)
    return {"committed_retry_table": table["id"], "uncommitted_retry_table": retry2.json()["id"]}


def main():
    require_disposable_ci()
    settings = config()
    database_url = (
        f"postgresql://{settings['POSTGRES_USER']}:{settings['POSTGRES_PASSWORD']}"
        f"@127.0.0.1:5432/{settings['POSTGRES_DB']}"
    )
    os.environ.update({
        "DATABASE_URL": database_url,
        "MINIO_ENDPOINT": "127.0.0.1:9000",
        "MINIO_ACCESS_KEY": settings["MINIO_ROOT_USER"],
        "MINIO_SECRET_KEY": settings["MINIO_ROOT_PASSWORD"],
        "MINIO_RAW_BUCKET": "raw",
        "MINIO_CURATED_BUCKET": "curated",
        "MINIO_SECURE": "false",
    })
    from app import main as api
    from scripts import audit_objects as audit

    storage = Minio(
        "127.0.0.1:9000",
        access_key=settings["MINIO_ROOT_USER"],
        secret_key=settings["MINIO_ROOT_PASSWORD"],
        secure=False,
    )
    with psycopg.connect(database_url, autocommit=True) as db, httpx.Client(
        base_url="http://127.0.0.1:8000", timeout=30
    ) as client, TestClient(api.app) as injected_api:
        wait_for("API readiness", lambda: client.get("/db-health").status_code == 200)
        upload_id = make_upload(client, "boundaries")
        run_id = UUID(post(client, f"/uploads/{upload_id}/process")["run_id"])
        wait_for(
            "source run to succeed",
            lambda: client.get(f"/processing-runs/{run_id}").json()["status"] == "succeeded",
        )
        curated_key = db_value(
            db, "SELECT curated_object_key FROM processing_runs WHERE id = %s", (run_id,)
        )
        assert curated_key

        admission = verify_query_admission(db, client, run_id)
        uncertain_upload_id, raw_key = verify_upload_uncertainty(
            db, client, injected_api, storage
        )
        inventory = verify_object_inventory(storage, audit, raw_key, curated_key)
        retries = verify_saved_table_retries(
            db, client, injected_api, storage, audit, run_id
        )
        print(json.dumps({
            "status": "passed",
            "run_id": str(run_id),
            "uncertain_upload_id": str(uncertain_upload_id),
            "admission": admission,
            "inventory": inventory,
            "saved_tables": retries,
        }, indent=2))


if __name__ == "__main__":
    main()
