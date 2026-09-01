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

def test_create_processing_run_inserts_running_record(
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
        "status": "running",
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

def test_process_upload_returns_curated_result(monkeypatch):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
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
    curated_object_key = (
        f"{dataset_id}/{upload_id}/data.parquet"
    )

    csv_content = b"order_id,amount\n1,10\n"
    parquet_content = b"PAR1simulated-parquet"

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
            "status": "running",
        }
    )

    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        fake_create_run,
    )

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

    response = client.post(
        f"/uploads/{upload_id}/process"
    )

    assert response.status_code == 200
    assert response.json() == {
        "upload_id": str(upload_id),
        "dataset_id": str(dataset_id),
        "object_key": curated_object_key,
        "format": "parquet",
        "row_count": 1,
        "run_id": str(run_id),
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

    fake_create_run.assert_called_once_with(upload_id)

    fake_complete_run.assert_called_once_with(
        run_id=run_id,
        row_count=1,
        curated_object_key=curated_object_key,
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

def test_process_upload_returns_422_for_unprocessable_csv(
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
    raw_object_key = (
        f"{dataset_id}/{upload_id}/broken.csv"
    )

    fake_curated_upload = Mock()

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
            "status": "running",
        }
    )
    fake_record_failure = Mock()

    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        fake_create_run,
    )
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

    response = client.post(
        f"/uploads/{upload_id}/process"
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "The uploaded CSV could not be processed.",
    }

    fake_metrics.assert_called_once_with(
        outcome="validation_failed",
        timer_started_at=10.0,
    )

    fake_curated_upload.assert_not_called()

    fake_create_run.assert_called_once_with(upload_id)

    fake_record_failure.assert_called_once_with(
        run_id=run_id,
        error_message=(
            "The uploaded CSV could not be processed."
        ),
        validation_failed=True,
    )


def test_process_upload_returns_503_when_curated_upload_fails(
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
    raw_object_key = (
        f"{dataset_id}/{upload_id}/sales.csv"
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
            "status": "running",
        }
    )

    fake_record_failure = Mock()

    monkeypatch.setattr(
        main_module,
        "create_processing_run",
        fake_create_run,
    )
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

    response = client.post(
        f"/uploads/{upload_id}/process"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Curated object storage is unavailable."
        ),
    }

    fake_metrics.assert_called_once_with(
        outcome="storage_failed",
        timer_started_at=10.0,
    )
    fake_create_run.assert_called_once_with(upload_id)

    fake_record_failure.assert_called_once_with(
        run_id=run_id,
        error_message=(
            "Curated object storage is unavailable."
        ),
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


def test_process_upload_records_internal_metric_when_run_creation_fails(
    monkeypatch,
):
    upload_id = UUID(
        "cd49f308-e39e-4d87-a7f0-f72f75bde678"
    )
    dataset_id = UUID(
        "a81cb365-f0a3-443a-a6ea-c077949e6207"
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

    response = client.post(
        f"/uploads/{upload_id}/process"
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Processing run creation failed.",
    }

    fake_metrics.assert_called_once_with(
        outcome="internal_failed",
        timer_started_at=10.0,
    )
