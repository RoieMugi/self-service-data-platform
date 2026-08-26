from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import app.main as main_module
from app.main import app
from fastapi.testclient import TestClient


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