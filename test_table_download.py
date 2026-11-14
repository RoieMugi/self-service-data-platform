"""Download the stored artifact through HTTP without requiring live services."""

from unittest.mock import Mock
from uuid import UUID

import duckdb
import pytest
from fastapi.testclient import TestClient

import app.main as main


TABLE_ID = UUID("aa20d66f-aa0e-4784-bbe0-7b6e5334e0d2")
OBJECT_KEY = f"tables/{TABLE_ID}/data.parquet"
URL = f"/tables/{TABLE_ID}/download"
client = TestClient(main.app)


@pytest.fixture
def dependencies(monkeypatch):
    lookup = Mock(return_value={"id": TABLE_ID, "object_key": OBJECT_KEY})
    stream = Mock()
    stream.read.return_value = b"stored bytes"
    storage = Mock()
    storage.get_object.return_value = stream
    executor = Mock(side_effect=AssertionError("Downloads must not execute SQL"))
    monkeypatch.setattr(main, "get_saved_table", lookup)
    monkeypatch.setattr(main, "get_minio_client", lambda: storage)
    monkeypatch.setattr(main, "execute_query", executor)
    monkeypatch.setattr(main, "execute_saved_query", executor)
    return lookup, storage, stream, executor


def test_download_preserves_parquet_and_attachment_headers(dependencies, tmp_path):
    lookup, storage, stream, executor = dependencies
    source = tmp_path / "source.parquet"
    with duckdb.connect() as connection:
        connection.sql(
            "SELECT 4::BIGINT AS customer_count, 650.0 AS total_amount, "
            "162.5 AS average_amount, 200.0 AS highest_amount"
        ).write_parquet(str(source))
    original = source.read_bytes()
    stream.read.return_value = original

    response = client.get(URL)

    assert response.status_code == 200
    assert response.content == original
    assert response.headers["content-type"] == "application/vnd.apache.parquet"
    assert response.headers["content-disposition"] == f'attachment; filename="{TABLE_ID}.parquet"'
    assert int(response.headers["content-length"]) == len(original)
    assert UUID(response.headers["x-correlation-id"])
    lookup.assert_called_once_with(TABLE_ID)
    storage.get_object.assert_called_once_with(main.MINIO_CURATED_BUCKET, OBJECT_KEY)
    stream.read.assert_called_once_with(main.MAX_PARQUET_BYTES + 1)
    stream.close.assert_called_once()
    stream.release_conn.assert_called_once()
    executor.assert_not_called()

    downloaded = tmp_path / "downloaded.parquet"
    downloaded.write_bytes(response.content)
    with duckdb.connect() as connection:
        row = connection.read_parquet(str(downloaded)).fetchone()
    assert row == (4, 650, 162.5, 200)


def test_missing_table_does_not_contact_storage(dependencies):
    lookup, storage, _, _ = dependencies
    lookup.return_value = None
    response = client.get(URL)
    assert response.status_code == 404
    assert response.json() == {"detail": "Saved table not found."}
    storage.get_object.assert_not_called()


def test_invalid_id_does_not_lookup_or_download(dependencies):
    lookup, storage, _, _ = dependencies
    assert client.get("/tables/not-a-uuid/download").status_code == 422
    lookup.assert_not_called()
    storage.get_object.assert_not_called()


def test_catalog_failure_is_controlled(dependencies):
    lookup, storage, _, _ = dependencies
    lookup.side_effect = RuntimeError("private database diagnostics")
    response = client.get(URL)
    assert response.status_code == 503
    assert response.json() == {"detail": "Table catalog unavailable."}
    storage.get_object.assert_not_called()


def test_storage_request_failure_is_controlled(dependencies):
    _, storage, stream, _ = dependencies
    storage.get_object.side_effect = OSError("private storage diagnostics")
    response = client.get(URL)
    assert response.status_code == 503
    assert response.json() == {"detail": "Query artifact could not be retrieved."}
    stream.read.assert_not_called()


@pytest.mark.parametrize("failure", ["read", "close"])
def test_connection_released_on_download_failure(dependencies, failure):
    _, _, stream, _ = dependencies
    getattr(stream, failure).side_effect = OSError("private transfer diagnostics")
    response = client.get(URL)
    assert response.status_code == 503
    assert "private transfer diagnostics" not in response.text
    assert "content-disposition" not in response.headers
    stream.close.assert_called_once()
    stream.release_conn.assert_called_once()


@pytest.mark.parametrize("size, expected_status", [(8, 200), (9, 413)])
def test_download_size_boundary(dependencies, monkeypatch, size, expected_status):
    _, _, stream, executor = dependencies
    # Exercise the real size check with a small limit instead of a 20 MiB allocation.
    monkeypatch.setattr(main, "MAX_PARQUET_BYTES", 8)
    stream.read.return_value = b"x" * size
    response = client.get(URL)
    assert response.status_code == expected_status
    stream.read.assert_called_once_with(9)
    stream.close.assert_called_once()
    stream.release_conn.assert_called_once()
    executor.assert_not_called()
    if expected_status == 200:
        assert response.content == b"x" * size
    else:
        assert response.json()["detail"] == "Dataset exceeds the 20 MiB query input limit."
        assert "content-disposition" not in response.headers
