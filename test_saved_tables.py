from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg.errors import UniqueViolation

import app.main as main


RUN_ID = UUID("79d674f8-9a9b-4b31-8951-31c381b21429")
TABLE_ID = UUID("a81cb365-f0a3-443a-a6ea-c077949e6207")
client = TestClient(main.app)
REQUEST = {"name": "regional_sales", "sql": "SELECT * FROM dataset"}


@pytest.fixture
def saved_dependencies(monkeypatch):
    monkeypatch.setattr(main, "get_processing_run", lambda _: {
        "status": "succeeded", "curated_object_key": "source.parquet",
    })
    monkeypatch.setattr(main, "download_query_artifact", lambda _: b"source")
    execute = Mock(return_value=(b"saved-parquet", 1500))
    upload = Mock()
    storage = Mock()
    monkeypatch.setattr(main, "execute_saved_query", execute)
    monkeypatch.setattr(main, "upload_curated_object", upload)
    monkeypatch.setattr(main, "get_minio_client", lambda: storage)
    # In-memory catalog for route behavior; it does not simulate database commits.
    rows = {}

    def insert(table_id, request, key, count, size, run_id, source_table_id):
        record = {
            "id": table_id, "name": request.name, "description": request.description,
            "source_run_id": run_id, "source_table_id": source_table_id,
            "query_sql": request.sql, "object_key": key, "row_count": count,
            "size_bytes": size, "created_at": datetime.now(timezone.utc),
        }
        rows[table_id] = record
        return record

    insert_mock = Mock(side_effect=insert)
    monkeypatch.setattr(main, "insert_saved_table", insert_mock)
    monkeypatch.setattr(main, "get_saved_table", lambda table_id: rows.get(table_id))
    return execute, upload, storage, insert_mock, rows


def test_save_read_query_and_derive(saved_dependencies, monkeypatch):
    execute, upload, _, insert, rows = saved_dependencies
    response = client.post(f"/processing-runs/{RUN_ID}/tables", json=REQUEST)
    assert response.status_code == 201
    data = response.json()
    assert data["row_count"] == 1500
    assert data["source_run_id"] == str(RUN_ID)
    assert data["source_table_id"] is None
    execute.assert_called_once_with(b"source", REQUEST["sql"])
    upload.assert_called_once_with(data["object_key"], b"saved-parquet")
    table_id = data["id"]
    assert client.get(f"/tables/{table_id}").json() == data
    preview = Mock(return_value={"columns": ["n"], "rows": [[1500]], "row_count": 1, "truncated": False})
    monkeypatch.setattr(main, "execute_query", preview)
    assert client.post(f"/tables/{table_id}/query", json={"sql": "SELECT COUNT(*) FROM dataset"}).status_code == 200
    derived = client.post(f"/tables/{table_id}/tables", json={**REQUEST, "name": "second"})
    assert derived.status_code == 201
    assert derived.json()["source_table_id"] == table_id
    assert derived.json()["source_run_id"] is None


def test_duplicate_name_cleans_up_only_new_object(saved_dependencies):
    _, upload, storage, insert, _ = saved_dependencies
    insert.side_effect = UniqueViolation("duplicate")
    response = client.post(f"/processing-runs/{RUN_ID}/tables", json=REQUEST)
    assert response.status_code == 409
    storage.remove_object.assert_called_once_with(main.MINIO_CURATED_BUCKET, upload.call_args.args[0])
    assert upload.call_args.args[0] != "source.parquet"


def test_uncertain_commit_preserves_object_and_returns_id(saved_dependencies):
    _, _, storage, insert, _ = saved_dependencies
    insert.side_effect = OSError("lost commit response")
    response = client.post(f"/processing-runs/{RUN_ID}/tables", json=REQUEST)
    assert response.status_code == 503
    assert "table_id" in response.json()["detail"]
    storage.remove_object.assert_not_called()


def test_upload_failure_does_not_register(saved_dependencies):
    _, upload, _, insert, _ = saved_dependencies
    upload.side_effect = OSError("storage down")
    assert client.post(f"/processing-runs/{RUN_ID}/tables", json=REQUEST).status_code == 503
    insert.assert_not_called()


def test_failed_query_does_not_upload_or_register(saved_dependencies):
    execute, upload, _, insert, _ = saved_dependencies
    execute.side_effect = main.QueryError("too many rows")
    assert client.post(f"/processing-runs/{RUN_ID}/tables", json=REQUEST).status_code == 422
    upload.assert_not_called()
    insert.assert_not_called()


def test_missing_saved_table_returns_404(saved_dependencies):
    assert client.get(f"/tables/{TABLE_ID}").status_code == 404
    assert client.post(f"/tables/{TABLE_ID}/query", json={"sql": "SELECT 1"}).status_code == 404


@pytest.mark.parametrize("changes", [{"name": " "}, {"max_rows": 1}, {"sql": ""}])
def test_save_validation_precedes_execution(saved_dependencies, changes):
    assert client.post(f"/processing-runs/{RUN_ID}/tables", json={**REQUEST, **changes}).status_code == 422
    saved_dependencies[0].assert_not_called()
