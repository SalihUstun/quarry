from fastapi.testclient import TestClient

from app.main import create_app
from tests.fakes import FakeDatabase, services_factory


def test_health_returns_ok() -> None:
    with TestClient(create_app(services_factory())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_ok_when_database_is_reachable() -> None:
    with TestClient(create_app(services_factory(FakeDatabase(reachable=True)))) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_503_when_database_is_unreachable() -> None:
    with TestClient(create_app(services_factory(FakeDatabase(reachable=False)))) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "database_unavailable"}
