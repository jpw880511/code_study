from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.api.exceptions import ERROR_MESSAGES
from src.config import AppSettings
from src.main import create_app

URL = "/api/v1/test-errors"


def make_client(environment: str) -> TestClient:
    settings = AppSettings(environment=environment, _env_file=None)  # type: ignore[call-arg]
    return TestClient(create_app(settings))


@pytest.fixture
def client() -> Iterator[TestClient]:
    with make_client("development") as test_client:
        yield test_client


def test_without_type_returns_success(client: TestClient) -> None:
    response = client.get(URL)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("error_type", "status", "code"),
    [
        ("notfound", 404, "not_found"),
        ("forbidden", 403, "forbidden"),
        ("conflict", 409, "conflict"),
    ],
)
def test_type_raises_matching_error(
    client: TestClient, error_type: str, status: int, code: str
) -> None:
    response = client.get(URL, params={"type": error_type})
    assert response.status_code == status
    assert response.json() == {"error": code, "message": ERROR_MESSAGES[code]}


def test_unknown_type_is_a_validation_error(client: TestClient) -> None:
    response = client.get(URL, params={"type": "bogus"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert [e["field"] for e in body["details"]["errors"]] == ["query.type"]


def test_endpoint_is_documented(client: TestClient) -> None:
    assert URL in client.get("/openapi.json").json()["paths"]


def test_endpoint_is_not_available_in_production() -> None:
    with make_client("production") as production_client:
        assert production_client.get(URL).status_code == 404
        assert URL not in production_client.get("/openapi.json").json()["paths"]
