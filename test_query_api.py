from unittest.mock import Mock
from uuid import UUID

import duckdb
import pytest
from fastapi.testclient import TestClient

import app.main as main_module


RUN_ID = UUID("79d674f8-9a9b-4b31-8951-31c381b21429")
URL = f"/processing-runs/{RUN_ID}/query"
client = TestClient(main_module.app)


@pytest.fixture
def dependencies(monkeypatch):
    lookup = Mock(return_value={
        "status": "succeeded", "curated_object_key": "dataset/upload/data.parquet",
    })
    storage_response = Mock()
    storage_response.read.return_value = b"parquet-placeholder"
    storage = Mock()
    storage.get_object.return_value = storage_response
    executor = Mock(return_value={
        "columns": ["amount"], "rows": [[10]], "row_count": 1, "truncated": False,
    })
    monkeypatch.setattr(main_module, "get_processing_run", lookup)
    monkeypatch.setattr(main_module, "get_minio_client", lambda: storage)
    monkeypatch.setattr(main_module, "execute_query", executor)
    return lookup, storage, storage_response, executor


def test_query_resolves_artifact_and_releases_download(dependencies):
    lookup, storage, stream, executor = dependencies
    response = client.post(URL, json={"sql": "SELECT amount FROM dataset", "max_rows": 5})
    assert response.status_code == 200
    assert response.json() == executor.return_value
    lookup.assert_called_once_with(RUN_ID)
    storage.get_object.assert_called_once_with(
        main_module.MINIO_CURATED_BUCKET, "dataset/upload/data.parquet",
    )
    stream.read.assert_called_once_with(main_module.MAX_PARQUET_BYTES + 1)
    stream.close.assert_called_once()
    stream.release_conn.assert_called_once()
    executor.assert_called_once_with(b"parquet-placeholder", "SELECT amount FROM dataset", 5)
    assert "x-correlation-id" in response.headers


@pytest.mark.parametrize("payload", [
    {"sql": " "},
    {"sql": "SELECT 1", "max_rows": 0},
    {"sql": "SELECT 1", "max_rows": 1001},
    {"sql": "SELECT 1", "max_rows": True},
    {"sql": "SELECT 1", "object_key": "another/file.parquet"},
])
def test_invalid_request_never_reads_storage(dependencies, payload):
    lookup, storage, _, executor = dependencies
    assert client.post(URL, json=payload).status_code == 422
    lookup.assert_not_called()
    storage.get_object.assert_not_called()
    executor.assert_not_called()


@pytest.mark.parametrize("run, status", [
    (None, 404),
    ({"status": "queued"}, 409),
    ({"status": "running"}, 409),
    ({"status": "failed"}, 409),
    ({"status": "succeeded", "curated_object_key": None}, 409),
])
def test_unavailable_run_never_reads_storage(dependencies, run, status):
    lookup, storage, _, executor = dependencies
    lookup.return_value = run
    assert client.post(URL, json={"sql": "SELECT 1"}).status_code == status
    storage.get_object.assert_not_called()
    executor.assert_not_called()


def test_lookup_failure_is_controlled(dependencies):
    lookup, storage, _, _ = dependencies
    lookup.side_effect = RuntimeError("private database details")
    response = client.post(URL, json={"sql": "SELECT 1"})
    assert response.status_code == 500
    assert "private database details" not in response.text
    storage.get_object.assert_not_called()


def test_download_failure_releases_connection(dependencies):
    _, _, stream, executor = dependencies
    stream.read.side_effect = OSError("private storage details")
    response = client.post(URL, json={"sql": "SELECT 1"})
    assert response.status_code == 503
    assert "private storage details" not in response.text
    stream.close.assert_called_once()
    stream.release_conn.assert_called_once()
    executor.assert_not_called()


def test_oversized_download_is_rejected_before_execution(dependencies):
    _, _, stream, executor = dependencies
    stream.read.return_value = b"x" * (main_module.MAX_PARQUET_BYTES + 1)
    assert client.post(URL, json={"sql": "SELECT 1"}).status_code == 413
    stream.release_conn.assert_called_once()
    executor.assert_not_called()


def test_query_error_is_controlled(dependencies):
    dependencies[3].side_effect = main_module.QueryError("Provide exactly one read-only SELECT query.")
    response = client.post(URL, json={"sql": "DROP TABLE dataset"})
    assert response.status_code == 422
    assert response.json()["detail"] == "Provide exactly one read-only SELECT query."


def test_unexpected_executor_failure_is_controlled(dependencies):
    dependencies[3].side_effect = OSError("private filesystem details")
    response = client.post(URL, json={"sql": "SELECT 1"})
    assert response.status_code == 500
    assert "private filesystem details" not in response.text


def test_api_with_real_query_process(dependencies, monkeypatch, tmp_path):
    from app.query_executor import execute_query

    path = tmp_path / "source.parquet"
    with duckdb.connect() as connection:
        connection.execute("CREATE TABLE sales AS SELECT * FROM (VALUES ('north', 10), ('north', 20), ('south', 5)) t(region, amount)")
        connection.table("sales").write_parquet(str(path))
    dependencies[2].read.return_value = path.read_bytes()
    monkeypatch.setattr(main_module, "execute_query", execute_query)
    response = client.post(URL, json={
        "sql": "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region ORDER BY region",
    })
    assert response.status_code == 200
    assert response.json() == {
        "columns": ["region", "total"], "rows": [["north", 30], ["south", 5]],
        "row_count": 2, "truncated": False,
    }
