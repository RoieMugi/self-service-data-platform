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
