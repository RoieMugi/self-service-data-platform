from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import Mock
import app.main as main_module

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