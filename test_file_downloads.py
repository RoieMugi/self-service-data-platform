from unittest.mock import Mock
from urllib.parse import unquote
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main


ID = UUID("246cbcbf-1fde-4acc-99dd-e6cb2b6e6c29")
client = TestClient(main.app)


@pytest.fixture
def dependencies(monkeypatch):
    upload = Mock(return_value={"object_key": "raw/source.csv", "original_filename": "sales.csv"})
    run = Mock(return_value={"status": "succeeded", "curated_object_key": "curated/data.parquet"})
    stream = Mock()
    stream.read.return_value = b"id,amount\r\n1,125.50\r\n"
    storage = Mock()
    storage.get_object.return_value = stream
    executor = Mock(side_effect=AssertionError("Download must not run SQL"))
    monkeypatch.setattr(main, "get_upload", upload)
    monkeypatch.setattr(main, "get_processing_run", run)
    monkeypatch.setattr(main, "get_minio_client", lambda: storage)
    monkeypatch.setattr(main, "execute_query", executor)
    monkeypatch.setattr(main, "execute_processing", executor)
    return upload, run, storage, stream, executor


@pytest.mark.parametrize("resource,bucket,key,limit,media,extension", [
    ("uploads", main.MINIO_RAW_BUCKET, "raw/source.csv", main.MAX_UPLOAD_SIZE, "text/csv", "csv"),
    ("processing-runs", main.MINIO_CURATED_BUCKET, "curated/data.parquet", main.MAX_PARQUET_BYTES, "application/vnd.apache.parquet", "parquet"),
])
def test_download_routes_preserve_bytes(dependencies, resource, bucket, key, limit, media, extension):
    upload, run, storage, stream, executor = dependencies
    response = client.get(f"/{resource}/{ID}/download")
    assert response.status_code == 200
    assert response.content == stream.read.return_value
    assert response.headers["content-type"].startswith(media)
    assert f'filename="{ID}.{extension}"' in response.headers["content-disposition"]
    assert "x-correlation-id" in response.headers
    storage.get_object.assert_called_once_with(bucket, key)
    stream.read.assert_called_once_with(limit + 1)
    stream.close.assert_called_once()
    stream.release_conn.assert_called_once()
    executor.assert_not_called()
    (upload if resource == "uploads" else run).assert_called_once_with(ID)


@pytest.mark.parametrize("filename,expected", [
    ('../folder/sales "Q1".csv', 'sales "Q1".csv'),
    ("C:\\folder\\sales.csv", "sales.csv"),
    ("sales\r\nInjected: value.csv", "salesInjected: value.csv"),
    ("מכירות.csv", "מכירות.csv"),
    ("", f"{ID}.csv"),
])
def test_original_filename_is_safely_encoded(dependencies, filename, expected):
    dependencies[0].return_value["original_filename"] = filename
    response = client.get(f"/uploads/{ID}/download")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    disposition.encode("ascii")
    assert unquote(disposition.split("filename*=UTF-8''", 1)[1]) == expected


@pytest.mark.parametrize("resource,index", [("uploads", 0), ("processing-runs", 1)])
def test_missing_metadata_never_downloads(dependencies, resource, index):
    dependencies[index].return_value = None
    assert client.get(f"/{resource}/{ID}/download").status_code == 404
    dependencies[2].get_object.assert_not_called()


@pytest.mark.parametrize("run", [
    {"status": "queued"}, {"status": "running"}, {"status": "failed"},
    {"status": "succeeded", "curated_object_key": None},
])
def test_unavailable_output_never_downloads(dependencies, run):
    dependencies[1].return_value = run
    assert client.get(f"/processing-runs/{ID}/download").status_code == 409
    dependencies[2].get_object.assert_not_called()


@pytest.mark.parametrize("resource,index,status", [("uploads", 0, 503), ("processing-runs", 1, 500)])
def test_metadata_failure_is_controlled(dependencies, resource, index, status):
    dependencies[index].side_effect = RuntimeError("private diagnostics")
    response = client.get(f"/{resource}/{ID}/download")
    assert response.status_code == status
    assert "private diagnostics" not in response.text
    dependencies[2].get_object.assert_not_called()


@pytest.mark.parametrize("resource", ["uploads", "processing-runs"])
@pytest.mark.parametrize("failure", ["get_object", "read", "close"])
def test_storage_failure_and_cleanup(dependencies, resource, failure):
    storage, stream = dependencies[2:4]
    target = storage if failure == "get_object" else stream
    getattr(target, failure).side_effect = OSError("private diagnostics")
    response = client.get(f"/{resource}/{ID}/download")
    assert response.status_code == 503
    assert "private diagnostics" not in response.text
    assert "content-disposition" not in response.headers
    if failure != "get_object":
        stream.close.assert_called_once()
        stream.release_conn.assert_called_once()


@pytest.mark.parametrize("resource,constant", [("uploads", "MAX_UPLOAD_SIZE"), ("processing-runs", "MAX_PARQUET_BYTES")])
@pytest.mark.parametrize("size,status", [(8, 200), (9, 413)])
def test_size_limits(dependencies, monkeypatch, resource, constant, size, status):
    monkeypatch.setattr(main, constant, 8)
    stream = dependencies[3]
    stream.read.return_value = b"x" * size
    assert client.get(f"/{resource}/{ID}/download").status_code == status
    stream.read.assert_called_once_with(9)
    stream.release_conn.assert_called_once()


@pytest.mark.parametrize("resource", ["uploads", "processing-runs"])
def test_invalid_id(dependencies, resource):
    assert client.get(f"/{resource}/invalid/download").status_code == 422
    dependencies[0].assert_not_called()
    dependencies[1].assert_not_called()
    dependencies[2].get_object.assert_not_called()
