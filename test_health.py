# API and processing contracts: database/storage calls are mocked; conversion uses
# real DuckDB. These checks do not replace live dependency and recovery exercises.

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock
from uuid import UUID

import duckdb
import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app

client = TestClient(app)


def test_health_returns_healthy_response():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_db_health_returns_healthy_when_connection_succeeds(monkeypatch):
    fake_connection = Mock()

    monkeypatch.setattr(
        main_module,
        "get_db_connection",
        lambda: fake_connection,
    )

    response = client.get("/db-health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "connected",
    }
    fake_connection.close.assert_called_once_with()


def test_db_health_returns_500_when_connection_fails(monkeypatch):
    def fail_to_connect():
        raise Exception("simulated database failure")

    monkeypatch.setattr(
        main_module,
        "get_db_connection",
        fail_to_connect,
    )

    response = client.get("/db-health")

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "status": "unhealthy",
            "error": "database unavailable",
        }
    }


def test_create_dataset_returns_created_dataset(monkeypatch):
    dataset_id = UUID("a81cb365-f0a3-443a-a6ea-c077949e6207")
    created_at = datetime(2026, 8, 25, 19, 2, 26, tzinfo=timezone.utc)

    def fake_insert_dataset(dataset):
        return {
            "id": dataset_id,
            "name": dataset.name,
            "description": dataset.description,
            "created_at": created_at,
        }

    monkeypatch.setattr(
        main_module,
        "insert_dataset",
        fake_insert_dataset,
    )

    response = client.post(
        "/datasets",
        json={
            "name": "sales",
            "description": "Sales transaction data",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(dataset_id),
        "name": "sales",
        "description": "Sales transaction data",
        "created_at": "2026-08-25T19:02:26Z",
    }


def test_create_dataset_returns_409_for_duplicate_name(monkeypatch):
    def fake_insert_dataset(dataset):
        raise main_module.UniqueViolation("simulated duplicate dataset")

    monkeypatch.setattr(
        main_module,
        "insert_dataset",
        fake_insert_dataset,
    )

    response = client.post(
        "/datasets",
        json={
            "name": "sales",
            "description": "Sales transaction data",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "A dataset with this name already exists.",
    }


def test_create_dataset_returns_422_for_empty_name(monkeypatch):
    fake_insert_dataset = Mock()

    monkeypatch.setattr(
        main_module,
        "insert_dataset",
        fake_insert_dataset,
    )

    response = client.post(
        "/datasets",
        json={
            "name": "   ",
            "description": "Invalid dataset",
        },
    )

    assert response.status_code == 422
    fake_insert_dataset.assert_not_called()

def test_upload_dataset_file_returns_created_upload(monkeypatch):
    dataset_id = UUID("a81cb365-f0a3-443a-a6ea-c077949e6207")
    upload_id = UUID("cd49f308-e39e-4d87-a7f0-f72f75bde678")
    created_at = datetime(2026, 8, 26, 20, 0, 0, tzinfo=timezone.utc)
    csv_content = b"order_id,amount\n1,10\n"

    fake_minio_client = Mock()

    monkeypatch.setattr(
        main_module,
        "dataset_exists",
        lambda requested_id: requested_id == dataset_id,
    )
    monkeypatch.setattr(
        main_module,
        "get_minio_client",
        lambda: fake_minio_client,
    )
    monkeypatch.setattr(
        main_module,
        "uuid4",
        lambda: upload_id,
    )

    def fake_insert_upload(**kwargs):
        return {
            "id": kwargs["upload_id"],
            "dataset_id": kwargs["dataset_id"],
            "original_filename": kwargs["original_filename"],
            "object_key": kwargs["object_key"],
            "content_type": kwargs["content_type"],
            "size_bytes": kwargs["size_bytes"],
            "created_at": created_at,
    }

    monkeypatch.setattr(
        main_module,
        "insert_upload",
        fake_insert_upload,
    )

    response = client.post(
        f"/datasets/{dataset_id}/uploads",
        files={
            "file": (
                "sales.csv",
                csv_content,
                "text/csv",
            ),
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(upload_id),
        "dataset_id": str(dataset_id),
        "original_filename": "sales.csv",
        "object_key": f"{dataset_id}/{upload_id}/sales.csv",
        "content_type": "text/csv",
        "size_bytes": len(csv_content),
        "created_at": "2026-08-26T20:00:00Z",
    }

    fake_minio_client.put_object.assert_called_once()

def test_upload_returns_404_when_dataset_does_not_exist(monkeypatch):
    dataset_id = UUID("a81cb365-f0a3-443a-a6ea-c077949e6207")
    fake_minio_client = Mock()

    monkeypatch.setattr(
        main_module,
        "dataset_exists",
        lambda requested_id: False,
    )
    monkeypatch.setattr(
        main_module,
        "get_minio_client",
        lambda: fake_minio_client,
    )

    response = client.post(
        f"/datasets/{dataset_id}/uploads",
        files={
            "file": (
                "sales.csv",
                b"order_id,amount\n1,10\n",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Dataset not found.",
    }
    fake_minio_client.put_object.assert_not_called()

def test_upload_returns_415_for_non_csv_file(monkeypatch):
    dataset_id = UUID("a81cb365-f0a3-443a-a6ea-c077949e6207")
    fake_minio_client = Mock()

    monkeypatch.setattr(
        main_module,
        "dataset_exists",
        lambda requested_id: True,
    )
    monkeypatch.setattr(
        main_module,
        "get_minio_client",
        lambda: fake_minio_client,
    )

    response = client.post(
        f"/datasets/{dataset_id}/uploads",
        files={
            "file": (
                "sales.txt",
                b"not a csv",
                "text/plain",
            ),
        },
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "Only CSV files are supported.",
    }
    fake_minio_client.put_object.assert_not_called()

def test_upload_returns_400_for_empty_csv(monkeypatch):
    dataset_id = UUID("a81cb365-f0a3-443a-a6ea-c077949e6207")
    fake_minio_client = Mock()

    monkeypatch.setattr(
        main_module,
        "dataset_exists",
        lambda requested_id: True,
    )
    monkeypatch.setattr(
        main_module,
        "get_minio_client",
        lambda: fake_minio_client,
    )

    response = client.post(
        f"/datasets/{dataset_id}/uploads",
        files={
            "file": (
                "sales.csv",
                b"",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The uploaded file is empty.",
    }
    fake_minio_client.put_object.assert_not_called()


def test_upload_removes_object_when_database_insert_fails(monkeypatch):
    dataset_id = UUID("a81cb365-f0a3-443a-a6ea-c077949e6207")
    upload_id = UUID("cd49f308-e39e-4d87-a7f0-f72f75bde678")
    fake_minio_client = Mock()

    monkeypatch.setattr(
        main_module,
        "dataset_exists",
        lambda requested_id: True,
    )
    monkeypatch.setattr(
        main_module,
        "get_minio_client",
        lambda: fake_minio_client,
    )
    monkeypatch.setattr(
        main_module,
        "uuid4",
        lambda: upload_id,
    )

    def fail_to_insert_upload(**kwargs):
        raise Exception("simulated database failure")

    monkeypatch.setattr(
        main_module,
        "insert_upload",
        fail_to_insert_upload,
    )

    response = client.post(
        f"/datasets/{dataset_id}/uploads",
        files={
            "file": (
                "sales.csv",
                b"order_id,amount\n1,10\n",
                "text/csv",
            ),
        },
    )

    object_key = f"{dataset_id}/{upload_id}/sales.csv"

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Upload registration failed.",
    }
    fake_minio_client.put_object.assert_called_once()
    fake_minio_client.remove_object.assert_called_once_with(
        "raw",
        object_key,
    )

def test_upload_returns_503_when_object_storage_fails(monkeypatch):
    dataset_id = UUID("a81cb365-f0a3-443a-a6ea-c077949e6207")
    fake_minio_client = Mock()
    fake_insert_upload = Mock()

    fake_minio_client.put_object.side_effect = Exception(
        "simulated object storage failure"
    )

    monkeypatch.setattr(
        main_module,
        "dataset_exists",
        lambda requested_id: True,
    )
    monkeypatch.setattr(
        main_module,
        "get_minio_client",
        lambda: fake_minio_client,
    )
    monkeypatch.setattr(
        main_module,
        "insert_upload",
        fake_insert_upload,
    )

    response = client.post(
        f"/datasets/{dataset_id}/uploads",
        files={
            "file": (
                "sales.csv",
                b"order_id,amount\n1,10\n",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Object storage is unavailable.",
    }
    fake_insert_upload.assert_not_called()

def test_get_upload_returns_upload_metadata(monkeypatch):
    upload_id = UUID("cd49f308-e39e-4d87-a7f0-f72f75bde678")
    dataset_id = UUID("a81cb365-f0a3-443a-a6ea-c077949e6207")

    expected_upload = {
        "id": upload_id,
        "dataset_id": dataset_id,
        "original_filename": "sales.csv",
        "object_key": f"{dataset_id}/{upload_id}/sales.csv",
        "content_type": "text/csv",
        "size_bytes": 22,
    }

    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = expected_upload

    fake_connection = MagicMock()
    fake_connection.__enter__.return_value = fake_connection
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    monkeypatch.setattr(
        main_module,
        "get_db_connection",
        lambda: fake_connection,
    )

    result = main_module.get_upload(upload_id)

    assert result == expected_upload
    fake_cursor.execute.assert_called_once()

    _, parameters = fake_cursor.execute.call_args.args
    assert parameters == (upload_id,)

def test_create_processing_run_inserts_queued_record(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )

    expected_run = {
        "id": run_id,
        "upload_id": upload_id,
        "status": "queued",
        "started_at": None,
        "created_at": datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
    }

    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = expected_run

    fake_connection = MagicMock()
    fake_connection.__enter__.return_value = (
        fake_connection
    )
    fake_connection.cursor.return_value.__enter__.return_value = (
        fake_cursor
    )

    monkeypatch.setattr(
        main_module,
        "get_db_connection",
        lambda: fake_connection,
    )

    result = main_module.create_processing_run(upload_id)

    assert result == expected_run
    fake_cursor.execute.assert_called_once()

    _, parameters = fake_cursor.execute.call_args.args
    assert parameters == (upload_id,)


@pytest.mark.parametrize("available", [True, False])
def test_claim_processing_run_returns_claim_or_none(monkeypatch, available):
    run_id = UUID("79d674f8-9a9b-4b31-8951-31c381b21429")
    expected = {"id": run_id, "status": "running"} if available else None
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = expected
    fake_connection = MagicMock()
    fake_connection.__enter__.return_value = fake_connection
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor
    monkeypatch.setattr(main_module, "get_db_connection", lambda: fake_connection)

    assert main_module.claim_processing_run(run_id) == expected
    fake_cursor.execute.assert_called_once()
    query, parameters = fake_cursor.execute.call_args.args
    normalized_query = " ".join(query.split())
    assert "WHERE id = %s AND status = 'queued'" in normalized_query
    assert "status = 'running'" in normalized_query
    assert "started_at = CURRENT_TIMESTAMP" in normalized_query
    assert parameters == (run_id,)


@pytest.mark.parametrize("claim_error", [False, True])
def test_execute_processing_stops_when_claim_fails(monkeypatch, claim_error):
    run_id = UUID("79d674f8-9a9b-4b31-8951-31c381b21429")
    fake_claim = Mock(return_value=None)
    if claim_error:
        fake_claim.side_effect = RuntimeError("Database unavailable")
    monkeypatch.setattr(main_module, "claim_processing_run", fake_claim)
    fake_run_lookup = Mock(return_value=None)
    monkeypatch.setattr(main_module, "get_processing_run", fake_run_lookup)
    downstream = {}
    for name in (
        "create_processing_run", "get_upload", "download_raw_object",
        "convert_csv_to_parquet", "upload_curated_object",
        "complete_processing_run", "try_to_record_processing_failure",
    ):
        downstream[name] = Mock()
        monkeypatch.setattr(main_module, name, downstream[name])

    with pytest.raises(main_module.ProcessingError) as caught:
        main_module.execute_processing(run_id, "test-correlation")

    assert caught.value.outcome == "internal_failed"
    fake_claim.assert_called_once_with(run_id)
    if claim_error:
        fake_run_lookup.assert_not_called()
    else:
        fake_run_lookup.assert_called_once_with(run_id)
    for mocked in downstream.values():
        mocked.assert_not_called()


@pytest.mark.parametrize("lookup_error", [False, True])
def test_execute_processing_records_failure_after_claimed_upload_lookup(
    monkeypatch, lookup_error,
):
    run_id = UUID("79d674f8-9a9b-4b31-8951-31c381b21429")
    upload_id = UUID("cd49f308-e39e-4d87-a7f0-f72f75bde678")
    monkeypatch.setattr(
        main_module, "claim_processing_run",
        Mock(return_value={"id": run_id, "upload_id": upload_id}),
    )
    fake_lookup = Mock(return_value=None)
    if lookup_error:
        fake_lookup.side_effect = RuntimeError("Database unavailable")
    monkeypatch.setattr(main_module, "get_upload", fake_lookup)
    fake_failure = Mock()
    fake_download = Mock()
    fake_metrics = Mock()
    monkeypatch.setattr(main_module, "try_to_record_processing_failure", fake_failure)
    monkeypatch.setattr(main_module, "download_raw_object", fake_download)
    monkeypatch.setattr(main_module, "record_processing_metrics", fake_metrics)

    with pytest.raises(main_module.ProcessingError) as caught:
        main_module.execute_processing(run_id, "test-correlation")

    assert caught.value.outcome == "internal_failed"
    fake_lookup.assert_called_once_with(upload_id)
    fake_failure.assert_called_once_with(
        run_id=run_id, error_message="Processing upload lookup failed.",
    )
    fake_download.assert_not_called()
    assert fake_metrics.call_args.kwargs["outcome"] == "internal_failed"


def test_execute_processing_uses_existing_run_without_creating_another(monkeypatch):
    run_id = UUID("79d674f8-9a9b-4b31-8951-31c381b21429")
    upload_id = UUID("cd49f308-e39e-4d87-a7f0-f72f75bde678")
    fake_create = Mock()
    fake_claim = Mock(return_value={"id": run_id, "upload_id": upload_id})
    fake_lookup = Mock(return_value={
        "id": upload_id, "dataset_id": "dataset", "object_key": "raw.csv",
    })
    fake_complete = Mock(return_value={"status": "succeeded", "validation_status": "passed"})
    monkeypatch.setattr(main_module, "create_processing_run", fake_create)
    monkeypatch.setattr(main_module, "claim_processing_run", fake_claim)
    monkeypatch.setattr(main_module, "get_upload", fake_lookup)
    monkeypatch.setattr(main_module, "download_raw_object", Mock(return_value=b"csv"))
    monkeypatch.setattr(main_module, "convert_csv_to_parquet", Mock(return_value=(b"PAR1", 1)))
    monkeypatch.setattr(main_module, "upload_curated_object", Mock())
    monkeypatch.setattr(main_module, "complete_processing_run", fake_complete)
    monkeypatch.setattr(main_module, "record_processing_metrics", Mock())

    result = main_module.execute_processing(run_id, "test-correlation")

    fake_create.assert_not_called()
    fake_claim.assert_called_once_with(run_id)
    fake_lookup.assert_called_once_with(upload_id)
    assert result["run_id"] == run_id
    assert result["status"] == "succeeded"
    fake_complete.assert_called_once_with(
        run_id=run_id, row_count=1,
        curated_object_key=f"dataset/{upload_id}/data.parquet",
    )


def test_download_raw_object_returns_bytes_and_releases_connection(
    monkeypatch,
):
    object_key = "dataset-id/upload-id/sales.csv"
    csv_content = b"order_id,amount\n1,10\n"

    fake_response = Mock()
    fake_response.read.return_value = csv_content

    fake_minio_client = Mock()
    fake_minio_client.get_object.return_value = fake_response

    monkeypatch.setattr(
        main_module,
        "get_minio_client",
        lambda: fake_minio_client,
    )

    result = main_module.download_raw_object(object_key)

    assert result == csv_content

    fake_minio_client.get_object.assert_called_once_with(
        "raw",
        object_key,
    )
    fake_response.read.assert_called_once_with()
    fake_response.close.assert_called_once_with()
    fake_response.release_conn.assert_called_once_with()

def test_convert_csv_to_parquet_returns_valid_parquet():
    csv_content = (
    b"\xef\xbb\xbf"
    b"order_id,amount\n"
    b"1,10\n"
    b"2,25\r\n"
)

    parquet_content, row_count = (
        main_module.convert_csv_to_parquet(csv_content)
    )

    assert row_count == 2
    assert parquet_content.startswith(b"PAR1")

    with TemporaryDirectory() as temporary_directory:
        parquet_path = (
            Path(temporary_directory) / "result.parquet"
        )
        parquet_path.write_bytes(parquet_content)

        with duckdb.connect() as connection:
            rows = connection.execute(
                """
                SELECT order_id, amount
                FROM read_parquet(?)
                ORDER BY order_id;
                """,
                [str(parquet_path)],
            ).fetchall()

    assert rows == [
        (1, 10),
        (2, 25),
    ]

def test_upload_curated_object_stores_parquet_in_curated_bucket(
    monkeypatch,
):
    object_key = "dataset-id/upload-id/data.parquet"
    parquet_content = b"PAR1simulated-parquet-content"

    fake_minio_client = Mock()

    monkeypatch.setattr(
        main_module,
        "get_minio_client",
        lambda: fake_minio_client,
    )

    main_module.upload_curated_object(
        object_key,
        parquet_content,
    )

    fake_minio_client.put_object.assert_called_once()

    positional_arguments = (
        fake_minio_client.put_object.call_args.args
    )
    keyword_arguments = (
        fake_minio_client.put_object.call_args.kwargs
    )

    bucket, stored_key, data_stream = positional_arguments

    assert bucket == "curated"
    assert stored_key == object_key
    assert data_stream.read() == parquet_content

    assert keyword_arguments == {
        "length": len(parquet_content),
        "content_type": "application/vnd.apache.parquet",
    }

def test_execute_processing_returns_curated_result(monkeypatch):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    dataset_id = UUID(
        "a81cb365-f0a3-443a-a6ea-c077949e6207"
    )
    correlation_id = (
        "0b87b403-bccc-4e92-a496-d41c27d18f42"
    )
    raw_object_key = (
        f"{dataset_id}/{upload_id}/sales.csv"
    )
    curated_object_key = (
        f"{dataset_id}/{upload_id}/data.parquet"
    )

    csv_content = b"order_id,amount\n1,10\n"
    parquet_content = b"PAR1simulated-parquet"

    fake_processing_log = Mock()

    monkeypatch.setattr(
        main_module,
        "log_processing_event",
        fake_processing_log,
    )

    monkeypatch.setattr(
        main_module,
        "get_upload",
        lambda requested_id: {
            "id": requested_id,
            "dataset_id": dataset_id,
            "object_key": raw_object_key,
        },
    )

    fake_create_run = Mock(
        return_value={
            "id": run_id,
            "upload_id": upload_id,
            "status": "queued",
        }
    )

    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        fake_create_run,
    )
    fake_claim_run = Mock(
        return_value={"id": run_id, "upload_id": upload_id, "status": "running"}
    )
    monkeypatch.setattr(main_module, "claim_processing_run", fake_claim_run)

    fake_download = Mock(return_value=csv_content)
    fake_conversion = Mock(
        return_value=(parquet_content, 1)
    )
    fake_curated_upload = Mock()

    fake_complete_run = Mock(
        return_value={
            "id": run_id,
            "upload_id": upload_id,
            "status": "succeeded",
            "row_count": 1,
            "curated_object_key": curated_object_key,
            "validation_status": "passed",
        }
    )

    monkeypatch.setattr(
        main_module,
        "download_raw_object",
        fake_download,
    )
    monkeypatch.setattr(
        main_module,
        "convert_csv_to_parquet",
        fake_conversion,
    )
    monkeypatch.setattr(
        main_module,
        "upload_curated_object",
        fake_curated_upload,
    )

    monkeypatch.setattr(
        main_module,
        "complete_processing_run",
        fake_complete_run,
    )

    fake_metrics = Mock()

    monkeypatch.setattr(
        main_module,
        "record_processing_metrics",
        fake_metrics,
    )
    monkeypatch.setattr(
        main_module,
        "monotonic",
        lambda: 10.0,
    )

    result = main_module.execute_processing(
        run_id=run_id, correlation_id=correlation_id,
    )

    assert result == {
        "upload_id": upload_id,
        "dataset_id": dataset_id,
        "object_key": curated_object_key,
        "format": "parquet",
        "row_count": 1,
        "run_id": run_id,
        "status": "succeeded",
        "validation_status": "passed",
    }

    fake_metrics.assert_called_once_with(
        outcome="succeeded",
        timer_started_at=10.0,
        row_count=1,
    )
    fake_download.assert_called_once_with(
        raw_object_key
    )
    fake_conversion.assert_called_once_with(
        csv_content
    )
    fake_curated_upload.assert_called_once_with(
        curated_object_key,
        parquet_content,
    )

    fake_create_run.assert_not_called()
    fake_claim_run.assert_called_once_with(run_id)

    fake_complete_run.assert_called_once_with(
        run_id=run_id,
        row_count=1,
        curated_object_key=curated_object_key,
    )
    fake_processing_log.assert_any_call(
        level=logging.INFO,
        event="processing_started",
        correlation_id=correlation_id,
        upload_id=upload_id,
        run_id=run_id,
    )

    fake_processing_log.assert_any_call(
        level=logging.INFO,
        event="processing_succeeded",
        correlation_id=correlation_id,
        upload_id=upload_id,
        run_id=run_id,
        outcome="succeeded",
        row_count=1,
    )


def test_process_upload_returns_404_when_upload_does_not_exist(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )

    fake_download = Mock()
    fake_conversion = Mock()
    fake_curated_upload = Mock()

    monkeypatch.setattr(
        main_module,
        "get_upload",
        lambda requested_id: None,
    )
    monkeypatch.setattr(
        main_module,
        "download_raw_object",
        fake_download,
    )
    monkeypatch.setattr(
        main_module,
        "convert_csv_to_parquet",
        fake_conversion,
    )
    monkeypatch.setattr(
        main_module,
        "upload_curated_object",
        fake_curated_upload,
    )

    response = client.post(
        f"/uploads/{upload_id}/process"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Upload not found.",
    }

    fake_download.assert_not_called()
    fake_conversion.assert_not_called()
    fake_curated_upload.assert_not_called()

def test_execute_processing_rejects_unprocessable_csv(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    dataset_id = UUID(
        "a81cb365-f0a3-443a-a6ea-c077949e6207"
    )
    correlation_id = (
        "0b87b403-bccc-4e92-a496-d41c27d18f42"
    )
    raw_object_key = (
        f"{dataset_id}/{upload_id}/broken.csv"
    )

    fake_curated_upload = Mock()

    fake_processing_log = Mock()

    monkeypatch.setattr(
        main_module,
        "log_processing_event",
        fake_processing_log,
    )

    monkeypatch.setattr(
        main_module,
        "get_upload",
        lambda requested_id: {
            "id": requested_id,
            "dataset_id": dataset_id,
            "object_key": raw_object_key,
        },
    )
    fake_create_run = Mock(
        return_value={
            "id": run_id,
            "upload_id": upload_id,
            "status": "queued",
        }
    )
    fake_record_failure = Mock()

    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        fake_create_run,
    )
    fake_claim_run = Mock(
        return_value={"id": run_id, "upload_id": upload_id, "status": "running"}
    )
    monkeypatch.setattr(main_module, "claim_processing_run", fake_claim_run)
    monkeypatch.setattr(
        main_module,
        "try_to_record_processing_failure",
        fake_record_failure,
    )
    monkeypatch.setattr(
        main_module,
        "download_raw_object",
        lambda object_key: b"invalid csv content",
    )

    def fail_conversion(csv_content):
        raise duckdb.InvalidInputException(
            "simulated CSV parsing failure"
        )

    monkeypatch.setattr(
        main_module,
        "convert_csv_to_parquet",
        fail_conversion,
    )
    monkeypatch.setattr(
        main_module,
        "upload_curated_object",
        fake_curated_upload,
    )

    fake_metrics = Mock()

    monkeypatch.setattr(
        main_module,
        "record_processing_metrics",
        fake_metrics,
    )
    monkeypatch.setattr(
        main_module,
        "monotonic",
        lambda: 10.0,
    )

    with pytest.raises(main_module.ProcessingError) as exc_info:
        main_module.execute_processing(
            run_id=run_id, correlation_id=correlation_id,
        )

    assert exc_info.value.outcome == "validation_failed"
    assert exc_info.value.message == "The uploaded CSV could not be processed."


    fake_metrics.assert_called_once_with(
        outcome="validation_failed",
        timer_started_at=10.0,
    )

    fake_curated_upload.assert_not_called()

    fake_create_run.assert_not_called()
    fake_claim_run.assert_called_once_with(run_id)

    fake_record_failure.assert_called_once_with(
        run_id=run_id,
        error_message=(
            "The uploaded CSV could not be processed."
        ),
        validation_failed=True,
    )

    fake_processing_log.assert_any_call(
        level=logging.WARNING,
        event="processing_failed",
        correlation_id=correlation_id,
        upload_id=upload_id,
        run_id=run_id,
        outcome="validation_failed",
    )

def test_execute_processing_records_curated_upload_failure(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )

    correlation_id = (
        "0b87b403-bccc-4e92-a496-d41c27d18f42"
    )

    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    dataset_id = UUID(
        "a81cb365-f0a3-443a-a6ea-c077949e6207"
    )
    raw_object_key = (
        f"{dataset_id}/{upload_id}/sales.csv"
    )

    fake_processing_log = Mock()

    monkeypatch.setattr(
        main_module,
        "log_processing_event",
        fake_processing_log,
    )

    monkeypatch.setattr(
        main_module,
        "get_upload",
        lambda requested_id: {
            "id": requested_id,
            "dataset_id": dataset_id,
            "object_key": raw_object_key,
        },
    )

    fake_create_run = Mock(
        return_value={
            "id": run_id,
            "upload_id": upload_id,
            "status": "queued",
        }
    )

    fake_record_failure = Mock()

    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        fake_create_run,
    )
    fake_claim_run = Mock(
        return_value={"id": run_id, "upload_id": upload_id, "status": "running"}
    )
    monkeypatch.setattr(main_module, "claim_processing_run", fake_claim_run)
    monkeypatch.setattr(
        main_module,
        "try_to_record_processing_failure",
        fake_record_failure,
    )

    monkeypatch.setattr(
        main_module,
        "download_raw_object",
        lambda object_key: b"order_id,amount\n1,10\n",
    )
    monkeypatch.setattr(
        main_module,
        "convert_csv_to_parquet",
        lambda csv_content: (
            b"PAR1simulated-parquet",
            1,
        ),
    )

    def fail_curated_upload(object_key, parquet_content):
        raise Exception(
            "simulated object storage failure"
        )

    monkeypatch.setattr(
        main_module,
        "upload_curated_object",
        fail_curated_upload,
    )

    fake_metrics = Mock()

    monkeypatch.setattr(
        main_module,
        "record_processing_metrics",
        fake_metrics,
    )
    monkeypatch.setattr(
        main_module,
        "monotonic",
        lambda: 10.0,
    )

    with pytest.raises(main_module.ProcessingError) as exc_info:
        main_module.execute_processing(
            run_id=run_id, correlation_id=correlation_id,
        )

    assert exc_info.value.outcome == "storage_failed"
    assert exc_info.value.message == "Curated object storage is unavailable."


    fake_metrics.assert_called_once_with(
        outcome="storage_failed",
        timer_started_at=10.0,
    )
    fake_create_run.assert_not_called()
    fake_claim_run.assert_called_once_with(run_id)

    fake_record_failure.assert_called_once_with(
        run_id=run_id,
        error_message=(
            "Curated object storage is unavailable."
        ),
    )

    fake_processing_log.assert_any_call(
        level=logging.ERROR,
        event="processing_failed",
        correlation_id=correlation_id,
        upload_id=upload_id,
        run_id=run_id,
        outcome="storage_failed",
    )

def test_execute_processing_records_raw_download_failure(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )

    correlation_id = (
        "0b87b403-bccc-4e92-a496-d41c27d18f42"
    )

    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    dataset_id = UUID(
        "a81cb365-f0a3-443a-a6ea-c077949e6207"
    )
    raw_object_key = (
        f"{dataset_id}/{upload_id}/sales.csv"
    )

    fake_processing_log = Mock()

    monkeypatch.setattr(
        main_module,
        "log_processing_event",
        fake_processing_log,
    )

    monkeypatch.setattr(
        main_module,
        "get_upload",
        lambda requested_id: {
            "id": requested_id,
            "dataset_id": dataset_id,
            "object_key": raw_object_key,
        },
    )

    fake_create_run = Mock(
        return_value={
            "id": run_id,
            "upload_id": upload_id,
            "status": "queued",
        }
    )

    fake_record_failure = Mock()

    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        fake_create_run,
    )
    fake_claim_run = Mock(
        return_value={"id": run_id, "upload_id": upload_id, "status": "running"}
    )
    monkeypatch.setattr(main_module, "claim_processing_run", fake_claim_run)
    monkeypatch.setattr(
        main_module,
        "try_to_record_processing_failure",
        fake_record_failure,
    )

    def fail_raw_download(object_key):
        raise Exception(
            "simulated raw object storage failure"
        )


    monkeypatch.setattr(
        main_module,
        "download_raw_object",
        fail_raw_download,
    )
    fake_conversion = Mock()

    monkeypatch.setattr(
        main_module,
        "convert_csv_to_parquet",
        fake_conversion,
    )

    fake_curated_upload = Mock()

    monkeypatch.setattr(
        main_module,
        "upload_curated_object",
        fake_curated_upload,
    )

    fake_metrics = Mock()

    monkeypatch.setattr(
        main_module,
        "record_processing_metrics",
        fake_metrics,
    )
    monkeypatch.setattr(
        main_module,
        "monotonic",
        lambda: 10.0,
    )

    with pytest.raises(main_module.ProcessingError) as exc_info:
        main_module.execute_processing(
            run_id=run_id, correlation_id=correlation_id,
        )

    assert exc_info.value.outcome == "storage_failed"
    assert exc_info.value.message == "Raw object storage is unavailable."


    fake_metrics.assert_called_once_with(
        outcome="storage_failed",
        timer_started_at=10.0,
    )
    fake_create_run.assert_not_called()
    fake_claim_run.assert_called_once_with(run_id)

    fake_record_failure.assert_called_once_with(
        run_id=run_id,
        error_message=(
            "Raw object storage is unavailable."
        ),
    )

    fake_conversion.assert_not_called()
    fake_curated_upload.assert_not_called()

    fake_processing_log.assert_any_call(
        level=logging.ERROR,
        event="processing_failed",
        correlation_id=correlation_id,
        upload_id=upload_id,
        run_id=run_id,
        outcome="storage_failed",
    )


def test_complete_processing_run_updates_success_fields(
    monkeypatch,
):
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    curated_object_key = (
        "dataset-id/upload-id/data.parquet"
    )

    expected_run = {
        "id": run_id,
        "status": "succeeded",
        "row_count": 42,
        "curated_object_key": curated_object_key,
        "validation_status": "passed",
    }

    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = expected_run

    fake_connection = MagicMock()
    fake_connection.__enter__.return_value = (
        fake_connection
    )
    fake_connection.cursor.return_value.__enter__.return_value = (
        fake_cursor
    )

    monkeypatch.setattr(
        main_module,
        "get_db_connection",
        lambda: fake_connection,
    )

    result = main_module.complete_processing_run(
        run_id=run_id,
        row_count=42,
        curated_object_key=curated_object_key,
    )

    assert result == expected_run
    fake_cursor.execute.assert_called_once()

    _, parameters = fake_cursor.execute.call_args.args
    assert parameters == (
        42,
        curated_object_key,
        run_id,
    )

def test_fail_processing_run_records_validation_failure(
    monkeypatch,
):
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    error_message = (
        "The uploaded CSV could not be processed."
    )

    expected_run = {
        "id": run_id,
        "status": "failed",
        "validation_status": "failed",
        "error_message": error_message,
    }

    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = expected_run

    fake_connection = MagicMock()
    fake_connection.__enter__.return_value = (
        fake_connection
    )
    fake_connection.cursor.return_value.__enter__.return_value = (
        fake_cursor
    )

    monkeypatch.setattr(
        main_module,
        "get_db_connection",
        lambda: fake_connection,
    )

    result = main_module.fail_processing_run(
        run_id=run_id,
        error_message=error_message,
        validation_failed=True,
    )

    assert result == expected_run
    fake_cursor.execute.assert_called_once()

    _, parameters = fake_cursor.execute.call_args.args
    assert parameters == (
        "failed",
        error_message,
        run_id,
    )

def test_fail_processing_run_leaves_validation_unknown(
    monkeypatch,
):
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    error_message = (
        "Curated object storage is unavailable."
    )

    expected_run = {
        "id": run_id,
        "status": "failed",
        "validation_status": None,
        "error_message": error_message,
    }

    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = expected_run

    fake_connection = MagicMock()
    fake_connection.__enter__.return_value = (
        fake_connection
    )
    fake_connection.cursor.return_value.__enter__.return_value = (
        fake_cursor
    )

    monkeypatch.setattr(
        main_module,
        "get_db_connection",
        lambda: fake_connection,
    )

    result = main_module.fail_processing_run(
        run_id=run_id,
        error_message=error_message,
    )

    assert result == expected_run
    fake_cursor.execute.assert_called_once()

    _, parameters = fake_cursor.execute.call_args.args
    assert parameters == (
        None,
        error_message,
        run_id,
    )


def test_read_processing_run_returns_run(monkeypatch):
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )
    created_at = datetime(
        2026,
        9,
        1,
        10,
        0,
        0,
        tzinfo=timezone.utc,
    )
    started_at = datetime(
        2026,
        9,
        1,
        10,
        0,
        0,
        tzinfo=timezone.utc,
    )
    completed_at = datetime(
        2026,
        9,
        1,
        10,
        0,
        5,
        tzinfo=timezone.utc,
    )

    fake_get_run = Mock(
        return_value={
            "id": run_id,
            "upload_id": upload_id,
            "status": "succeeded",
            "created_at": created_at,
            "started_at": started_at,
            "completed_at": completed_at,
            "row_count": 42,
            "curated_object_key": (
                "dataset-id/upload-id/data.parquet"
            ),
            "validation_status": "passed",
            "error_message": None,
        }
    )

    monkeypatch.setattr(
        main_module,
        "get_processing_run",
        fake_get_run,
    )

    response = client.get(
        f"/processing-runs/{run_id}"
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(run_id),
        "upload_id": str(upload_id),
        "status": "succeeded",
        "created_at": "2026-09-01T10:00:00Z",
        "started_at": "2026-09-01T10:00:00Z",
        "completed_at": "2026-09-01T10:00:05Z",
        "row_count": 42,
        "curated_object_key": (
            "dataset-id/upload-id/data.parquet"
        ),
        "validation_status": "passed",
        "error_message": None,
    }

    fake_get_run.assert_called_once_with(run_id)

def test_read_processing_run_returns_queued_run(monkeypatch):
    run_id = UUID("79d674f8-9a9b-4b31-8951-31c381b21429")
    upload_id = UUID("cd49f308-e39e-4d87-a7f0-f72f75bde678")
    created_at = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)

    fake_get_run = Mock(
        return_value={
            "id": run_id,
            "upload_id": upload_id,
            "status": "queued",
            "created_at": created_at,
            "started_at": None,
            "completed_at": None,
            "row_count": None,
            "curated_object_key": None,
            "validation_status": None,
            "error_message": None,
        }
    )
    monkeypatch.setattr(main_module, "get_processing_run", fake_get_run)

    response = client.get(f"/processing-runs/{run_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(run_id),
        "upload_id": str(upload_id),
        "status": "queued",
        "created_at": "2026-09-08T10:00:00Z",
        "started_at": None,
        "completed_at": None,
        "row_count": None,
        "curated_object_key": None,
        "validation_status": None,
        "error_message": None,
    }
    fake_get_run.assert_called_once_with(run_id)


def test_read_processing_run_returns_404_when_missing(
    monkeypatch,
):
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )

    fake_get_run = Mock(return_value=None)

    monkeypatch.setattr(
        main_module,
        "get_processing_run",
        fake_get_run,
    )

    response = client.get(
        f"/processing-runs/{run_id}"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Processing run not found.",
    }

    fake_get_run.assert_called_once_with(run_id)

def test_get_processing_run_returns_database_record(
    monkeypatch,
):
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )

    expected_run = {
        "id": run_id,
        "upload_id": upload_id,
        "status": "running",
        "created_at": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
    }

    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = expected_run

    fake_connection = MagicMock()
    fake_connection.__enter__.return_value = (
        fake_connection
    )
    fake_connection.cursor.return_value.__enter__.return_value = (
        fake_cursor
    )

    monkeypatch.setattr(
        main_module,
        "get_db_connection",
        lambda: fake_connection,
    )

    result = main_module.get_processing_run(run_id)

    assert result == expected_run
    fake_cursor.execute.assert_called_once()

    _, parameters = fake_cursor.execute.call_args.args
    assert parameters == (run_id,)


def test_metrics_returns_prometheus_metrics():
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/plain"
    )

    metrics_text = response.text

    assert "# HELP platform_processing_runs_total" in metrics_text
    assert "# TYPE platform_processing_runs_total counter" in metrics_text

    assert (
        "# HELP platform_processing_duration_seconds"
        in metrics_text
    )
    assert (
        "# TYPE platform_processing_duration_seconds histogram"
        in metrics_text
    )

    assert "# HELP platform_processed_rows_total" in metrics_text
    assert "# TYPE platform_processed_rows_total counter" in metrics_text

    assert (
        "# HELP platform_last_successful_processing_timestamp_seconds"
        in metrics_text
    )
    assert (
        "# TYPE platform_last_successful_processing_timestamp_seconds gauge"
        in metrics_text
    )


def test_record_processing_metrics_records_success(
    monkeypatch,
):
    fake_runs = Mock()
    fake_duration = Mock()
    fake_rows = Mock()
    fake_last_success = Mock()

    monkeypatch.setattr(
        main_module,
        "PROCESSING_RUNS",
        fake_runs,
    )
    monkeypatch.setattr(
        main_module,
        "PROCESSING_DURATION",
        fake_duration,
    )
    monkeypatch.setattr(
        main_module,
        "PROCESSED_ROWS",
        fake_rows,
    )
    monkeypatch.setattr(
        main_module,
        "LAST_SUCCESSFUL_PROCESSING",
        fake_last_success,
    )
    monkeypatch.setattr(
        main_module,
        "monotonic",
        lambda: 15.5,
    )
    monkeypatch.setattr(
        main_module,
        "time",
        lambda: 1_788_296_400,
    )

    main_module.record_processing_metrics(
        outcome="succeeded",
        timer_started_at=10.0,
        row_count=42,
    )

    fake_runs.labels.assert_called_once_with(
        outcome="succeeded"
    )
    fake_runs.labels.return_value.inc.assert_called_once_with()

    fake_duration.labels.assert_called_once_with(
        outcome="succeeded"
    )
    (
        fake_duration.labels.return_value.observe
        .assert_called_once_with(5.5)
    )

    fake_rows.inc.assert_called_once_with(42)
    fake_last_success.set.assert_called_once_with(
        1_788_296_400
    )


@pytest.mark.parametrize(
    "outcome",
    [
        "validation_failed",
        "storage_failed",
        "internal_failed",
    ],
)
def test_record_processing_metrics_records_failure(
    monkeypatch,
    outcome,
):
    fake_runs = Mock()
    fake_duration = Mock()
    fake_rows = Mock()
    fake_last_success = Mock()

    monkeypatch.setattr(
        main_module,
        "PROCESSING_RUNS",
        fake_runs,
    )
    monkeypatch.setattr(
        main_module,
        "PROCESSING_DURATION",
        fake_duration,
    )
    monkeypatch.setattr(
        main_module,
        "PROCESSED_ROWS",
        fake_rows,
    )
    monkeypatch.setattr(
        main_module,
        "LAST_SUCCESSFUL_PROCESSING",
        fake_last_success,
    )
    monkeypatch.setattr(
        main_module,
        "monotonic",
        lambda: 14.25,
    )

    main_module.record_processing_metrics(
        outcome=outcome,
        timer_started_at=10.0,
    )

    fake_runs.labels.assert_called_once_with(
        outcome=outcome
    )
    fake_runs.labels.return_value.inc.assert_called_once_with()

    fake_duration.labels.assert_called_once_with(
        outcome=outcome
    )
    (
        fake_duration.labels.return_value.observe
        .assert_called_once_with(4.25)
    )

    fake_rows.inc.assert_not_called()
    fake_last_success.set.assert_not_called()


def test_execute_processing_logs_validation_failure_for_empty_rows(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    dataset_id = UUID(
        "a81cb365-f0a3-443a-a6ea-c077949e6207"
    )
    correlation_id = (
        "0b87b403-bccc-4e92-a496-d41c27d18f42"
    )
    fake_record_failure = Mock()
    fake_curated_upload = Mock()
    fake_metrics = Mock()
    fake_processing_log = Mock()

    monkeypatch.setattr(
        main_module,
        "get_upload",
        lambda requested_id: {
            "id": requested_id,
            "dataset_id": dataset_id,
            "object_key": "dataset/upload/empty.csv",
        },
    )
    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        lambda requested_id: {"id": run_id},
    )
    fake_claim_run = Mock(
        return_value={"id": run_id, "upload_id": upload_id, "status": "running"}
    )
    monkeypatch.setattr(main_module, "claim_processing_run", fake_claim_run)
    monkeypatch.setattr(
        main_module,
        "download_raw_object",
        lambda object_key: b"order_id,amount\n",
    )
    monkeypatch.setattr(
        main_module,
        "convert_csv_to_parquet",
        lambda csv_content: (b"PAR1", 0),
    )
    monkeypatch.setattr(
        main_module,
        "upload_curated_object",
        fake_curated_upload,
    )
    monkeypatch.setattr(
        main_module,
        "try_to_record_processing_failure",
        fake_record_failure,
    )
    monkeypatch.setattr(
        main_module,
        "record_processing_metrics",
        fake_metrics,
    )
    monkeypatch.setattr(
        main_module,
        "log_processing_event",
        fake_processing_log,
    )
    monkeypatch.setattr(
        main_module,
        "monotonic",
        lambda: 10.0,
    )

    with pytest.raises(main_module.ProcessingError) as exc_info:
        main_module.execute_processing(
            run_id=run_id, correlation_id=correlation_id,
        )

    assert exc_info.value.outcome == "validation_failed"
    assert exc_info.value.message == "The uploaded CSV contains no data rows."

    fake_curated_upload.assert_not_called()
    fake_record_failure.assert_called_once_with(
        run_id=run_id,
        error_message=(
            "The uploaded CSV contains no data rows."
        ),
        validation_failed=True,
    )
    fake_processing_log.assert_any_call(
        level=logging.WARNING,
        event="processing_failed",
        correlation_id=correlation_id,
        upload_id=upload_id,
        run_id=run_id,
        outcome="validation_failed",
    )


def test_execute_processing_logs_internal_result_tracking_failure(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    dataset_id = UUID(
        "a81cb365-f0a3-443a-a6ea-c077949e6207"
    )
    correlation_id = (
        "0b87b403-bccc-4e92-a496-d41c27d18f42"
    )
    fake_metrics = Mock()
    fake_processing_log = Mock()

    monkeypatch.setattr(
        main_module,
        "get_upload",
        lambda requested_id: {
            "id": requested_id,
            "dataset_id": dataset_id,
            "object_key": "dataset/upload/sales.csv",
        },
    )
    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        lambda requested_id: {"id": run_id},
    )
    fake_claim_run = Mock(
        return_value={"id": run_id, "upload_id": upload_id, "status": "running"}
    )
    monkeypatch.setattr(main_module, "claim_processing_run", fake_claim_run)
    monkeypatch.setattr(
        main_module,
        "download_raw_object",
        lambda object_key: b"order_id,amount\n1,10\n",
    )
    monkeypatch.setattr(
        main_module,
        "convert_csv_to_parquet",
        lambda csv_content: (b"PAR1", 1),
    )
    monkeypatch.setattr(
        main_module,
        "upload_curated_object",
        Mock(),
    )

    def fail_result_tracking(**kwargs):
        raise Exception("simulated result tracking failure")

    monkeypatch.setattr(
        main_module,
        "complete_processing_run",
        fail_result_tracking,
    )
    monkeypatch.setattr(
        main_module,
        "record_processing_metrics",
        fake_metrics,
    )
    monkeypatch.setattr(
        main_module,
        "log_processing_event",
        fake_processing_log,
    )
    monkeypatch.setattr(
        main_module,
        "monotonic",
        lambda: 10.0,
    )

    with pytest.raises(main_module.ProcessingError) as exc_info:
        main_module.execute_processing(
            run_id=run_id, correlation_id=correlation_id,
        )

    assert exc_info.value.outcome == "internal_failed"
    assert exc_info.value.message == "Processing result tracking failed."

    fake_processing_log.assert_any_call(
        level=logging.ERROR,
        event="processing_failed",
        correlation_id=correlation_id,
        upload_id=upload_id,
        run_id=run_id,
        outcome="internal_failed",
    )


def test_process_upload_records_internal_metric_when_run_creation_fails(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )
    dataset_id = UUID(
        "a81cb365-f0a3-443a-a6ea-c077949e6207"
    )
    correlation_id = (
        "0b87b403-bccc-4e92-a496-d41c27d18f42"
    )

    monkeypatch.setattr(
        main_module,
        "get_upload",
        lambda requested_id: {
            "id": requested_id,
            "dataset_id": dataset_id,
            "object_key": "dataset/upload/sales.csv",
        },
    )

    def fail_run_creation(requested_upload_id):
        raise Exception(
            "simulated processing-run creation failure"
        )

    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        fail_run_creation,
    )

    fake_metrics = Mock()
    fake_processing_log = Mock()

    monkeypatch.setattr(
        main_module,
        "record_processing_metrics",
        fake_metrics,
    )
    monkeypatch.setattr(
        main_module,
        "log_processing_event",
        fake_processing_log,
    )
    monkeypatch.setattr(
        main_module,
        "monotonic",
        lambda: 10.0,
    )

    response = client.post(
        f"/uploads/{upload_id}/process",
        headers={"X-Correlation-ID": correlation_id},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Processing run creation failed.",
    }

    fake_metrics.assert_called_once_with(
        outcome="internal_failed",
        timer_started_at=10.0,
    )
    fake_processing_log.assert_called_once_with(
        level=logging.ERROR,
        event="processing_failed",
        correlation_id=correlation_id,
        upload_id=upload_id,
        outcome="internal_failed",
    )


def test_health_generates_correlation_id():
    response = client.get("/health")

    correlation_id = response.headers.get(
        "X-Correlation-ID"
    )

    assert correlation_id is not None
    UUID(correlation_id)

def test_health_reuses_valid_correlation_id():
    correlation_id = (
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": correlation_id,
        },
    )

    assert response.headers["X-Correlation-ID"] == (
        correlation_id
    )

def test_health_replaces_invalid_correlation_id():
    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": "not-a-valid-uuid",
        },
    )

    returned_id = response.headers[
        "X-Correlation-ID"
    ]

    assert returned_id != "not-a-valid-uuid"
    UUID(returned_id)

def test_request_completion_log_contains_context(
    caplog,
):
    correlation_id = (
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )

    main_module.logger.addHandler(caplog.handler)

    try:
        with caplog.at_level(
            logging.INFO,
            logger="platform.api",
        ):
            response = client.get(
                "/health",
                headers={
                    "X-Correlation-ID": correlation_id,
                },
            )
    finally:
        main_module.logger.removeHandler(
            caplog.handler
        )

    request_log = next(
        record
        for record in caplog.records
        if record.getMessage()
        == "http_request_completed"
    )

    assert response.status_code == 200
    assert request_log.correlation_id == correlation_id
    assert request_log.method == "GET"
    assert request_log.path == "/health"
    assert request_log.status_code == 200
    assert request_log.duration_ms >= 0

def test_json_log_formatter_serializes_request_fields():
    record = logging.LogRecord(
        name="platform.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="http_request_completed",
        args=(),
        exc_info=None,
    )

    record.correlation_id = (
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200
    record.duration_ms = 12.5

    formatter = main_module.JsonLogFormatter()
    output = json.loads(formatter.format(record))

    assert output["level"] == "INFO"
    assert output["event"] == "http_request_completed"
    assert output["correlation_id"] == (
        record.correlation_id
    )
    assert output["method"] == "GET"
    assert output["path"] == "/health"
    assert output["status_code"] == 200
    assert output["duration_ms"] == 12.5
    assert "timestamp" in output

def test_application_logger_uses_json_formatter():
    assert main_module.logger.level == logging.INFO
    assert main_module.logger.propagate is False
    assert len(main_module.logger.handlers) == 1

    handler = main_module.logger.handlers[0]

    assert isinstance(
        handler.formatter,
        main_module.JsonLogFormatter,
    )

def test_log_processing_event_emits_context(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )
    run_id = UUID(
        "79d674f8-9a9b-4b31-8951-31c381b21429"
    )
    fake_logger = Mock()

    monkeypatch.setattr(
        main_module,
        "logger",
        fake_logger,
    )

    main_module.log_processing_event(
        level=logging.INFO,
        event="processing_started",
        correlation_id="0b87b403-bccc-4e92-a496-d41c27d18f42",
        upload_id=upload_id,
        run_id=run_id,
    )

    fake_logger.log.assert_called_once_with(
        logging.INFO,
        "processing_started",
        extra={
            "correlation_id": (
                "0b87b403-bccc-4e92-a496-d41c27d18f42"
            ),
            "upload_id": str(upload_id),
            "run_id": str(run_id),
        },
    )
