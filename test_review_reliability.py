"""Focused contracts for the review-phase failure boundaries."""

from threading import BoundedSemaphore
from unittest.mock import MagicMock, Mock
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as api
import scripts.audit_objects as audit


RUN = UUID("79d674f8-9a9b-4b31-8951-31c381b21429")
TOKEN = UUID("3c388a0b-0333-495d-abf4-f44c258d1840")


def database(monkeypatch, fetchone=None, fetchall=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr(api, "get_db_connection", lambda: connection)
    return cursor


def test_queued_run_and_publication_intent_share_one_transaction(monkeypatch):
    cursor = database(monkeypatch, fetchone={"id": RUN, "status": "queued"})
    api.create_processing_run(RUN, str(TOKEN))
    assert cursor.execute.call_count == 2
    assert "processing_outbox" in cursor.execute.call_args_list[1].args[0]
    assert cursor.execute.call_args_list[1].args[1] == (RUN, str(TOKEN))


def test_uncertain_broker_publish_leaves_intent_pending(monkeypatch):
    cursor = database(monkeypatch, fetchone={"run_id": RUN, "correlation_id": TOKEN})
    monkeypatch.setattr(api, "publish_processing_run", Mock(side_effect=RuntimeError("confirmation lost")))
    with pytest.raises(RuntimeError, match="confirmation lost"):
        api.publish_pending_run(RUN)
    assert cursor.execute.call_count == 1


def test_expired_runs_retry_then_fail_after_attempt_budget(monkeypatch):
    cursor = database(monkeypatch, fetchall=[{"id": RUN, "attempt_count": 1},
                                             {"id": TOKEN, "attempt_count": api.MAX_RUN_ATTEMPTS}])
    assert api.recover_expired_runs() == 2
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("status = 'queued'" in statement for statement in statements)
    assert any("processing_outbox" in statement for statement in statements)
    assert any("status = 'failed'" in statement for statement in statements)


def test_stale_claim_is_fenced_from_final_database_update(monkeypatch):
    cursor = database(monkeypatch, fetchone=None)
    context = api.ACTIVE_CLAIM_TOKEN.set(TOKEN)
    try:
        assert api.complete_processing_run(RUN, 3, "attempt-1/data.parquet") is None
    finally:
        api.ACTIVE_CLAIM_TOKEN.reset(context)
    statement, parameters = cursor.execute.call_args.args
    assert "claim_token = %s" in statement
    assert "lease_expires_at > CURRENT_TIMESTAMP" in statement
    assert parameters[-1] == TOKEN


def test_processing_attempts_never_share_an_object_key():
    upload = {"id": TOKEN, "dataset_id": RUN}
    first = api.processing_attempt_key(upload, RUN, 1)
    second = api.processing_attempt_key(upload, RUN, 2)
    assert first != second
    assert first.endswith("/attempt-1/data.parquet")
    assert second.endswith("/attempt-2/data.parquet")


def test_object_inventory_reports_missing_and_orphaned_without_deletion(monkeypatch):
    cursor = database(monkeypatch)
    cursor.fetchall.side_effect = [[("raw/kept.csv",)], [("curated/missing.parquet",)],
                                   [("tables/kept.parquet",)]]
    client = Mock()
    client.list_objects.side_effect = [
        [Mock(object_name="raw/kept.csv"), Mock(object_name="raw/orphan.csv")],
        [Mock(object_name="tables/kept.parquet")],
    ]
    monkeypatch.setattr(audit, "get_db_connection", api.get_db_connection)
    monkeypatch.setattr(audit, "get_minio_client", lambda: client)
    report = audit.inventory()
    assert report[audit.MINIO_RAW_BUCKET]["unreferenced_stored"] == ["raw/orphan.csv"]
    assert report[audit.MINIO_CURATED_BUCKET]["referenced_missing"] == ["curated/missing.parquet"]
    client.remove_object.assert_not_called()


def test_query_admission_rejects_overload_and_releases_on_error(monkeypatch):
    slots = BoundedSemaphore(1)
    monkeypatch.setattr(api, "QUERY_SLOTS", slots)
    wrapped = api.admit_query(lambda: "ok")
    slots.acquire()
    with pytest.raises(HTTPException) as error:
        wrapped()
    assert error.value.status_code == 429
    slots.release()
    assert wrapped() == "ok"
    failing = api.admit_query(lambda: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        failing()
    assert wrapped() == "ok"


def test_idempotent_save_returns_existing_table_before_recomputing(monkeypatch):
    request = api.SaveQueryTableRequest(name="regions", sql="SELECT * FROM dataset")
    existing = {"id": RUN, "name": "regions"}
    monkeypatch.setattr(api, "matching_operation", Mock(return_value=existing))
    download = Mock(side_effect=AssertionError("Retry must not compute or upload"))
    monkeypatch.setattr(api, "load_query_artifact", download)
    assert api.save_query_table("source.parquet", request, source_run_id=RUN, operation_id=TOKEN) is existing
    download.assert_not_called()


def test_idempotency_key_reuse_with_different_request_is_rejected(monkeypatch):
    database(monkeypatch, fetchone={"name": "other", "description": None,
                                     "query_sql": "SELECT * FROM dataset", "source_run_id": RUN,
                                     "source_table_id": None})
    request = api.SaveQueryTableRequest(name="regions", sql="SELECT * FROM dataset")
    with pytest.raises(HTTPException) as error:
        api.matching_operation(TOKEN, request, RUN, None)
    assert error.value.status_code == 409


def test_uncertain_table_commit_is_resolved_by_operation_lookup(monkeypatch):
    request = api.SaveQueryTableRequest(name="regions", sql="SELECT * FROM dataset")
    existing = {"id": RUN, "name": "regions"}
    monkeypatch.setattr(api, "matching_operation", Mock(side_effect=[None, existing]))
    monkeypatch.setattr(api, "load_query_artifact", lambda key: b"source")
    monkeypatch.setattr(api, "execute_saved_query", lambda content, sql: (b"parquet", 2))
    monkeypatch.setattr(api, "upload_curated_object", Mock())
    monkeypatch.setattr(api, "insert_saved_table", Mock(side_effect=RuntimeError("commit reply lost")))
    storage = Mock()
    monkeypatch.setattr(api, "get_minio_client", lambda: storage)
    assert api.save_query_table("source.parquet", request, source_run_id=RUN, operation_id=TOKEN) is existing
    storage.remove_object.assert_not_called()


def test_save_route_forwards_idempotency_key(monkeypatch):
    monkeypatch.setattr(api, "processing_artifact_key", lambda run_id: "source.parquet")
    save = Mock(return_value={"id": RUN, "name": "regions", "description": None,
                              "source_run_id": RUN, "source_table_id": None,
                              "query_sql": "SELECT * FROM dataset", "object_key": "tables/x.parquet",
                              "row_count": 2, "size_bytes": 100,
                              "created_at": "2026-11-14T00:00:00Z"})
    monkeypatch.setattr(api, "save_query_table", save)
    response = TestClient(api.app).post(
        f"/processing-runs/{RUN}/tables",
        json={"name": "regions", "sql": "SELECT * FROM dataset"},
        headers={"Idempotency-Key": str(TOKEN)},
    )
    assert response.status_code == 201
    assert save.call_args.kwargs["operation_id"] == TOKEN
