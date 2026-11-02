from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class FakeDatabase:
    def __init__(self, reachable: bool) -> None:
        self.reachable = reachable

    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def is_reachable(self) -> bool:
        return self.reachable


def make_client(reachable: bool) -> Iterator[TestClient]:
    with TestClient(create_app(FakeDatabase(reachable))) as client:
        yield client


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield from make_client(reachable=True)


@pytest.fixture
def client_without_database() -> Iterator[TestClient]:
    yield from make_client(reachable=False)


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_ok_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_503_when_database_is_unreachable(
    client_without_database: TestClient,
) -> None:
    response = client_without_database.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "database_unavailable"}
