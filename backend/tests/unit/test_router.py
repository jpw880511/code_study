from collections.abc import Iterator

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from src.api.router import API_PREFIX, api_router
from src.config import AppSettings
from src.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_router_is_versioned() -> None:
    assert API_PREFIX == "/api/v1"
    assert isinstance(api_router, APIRouter)
    assert api_router.prefix == API_PREFIX


def test_versioned_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_health_endpoint_still_works(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_router_is_mounted_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/health" in paths
    assert "/health" in paths


def test_unversioned_api_path_is_not_served(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 404


def test_unknown_v1_path_returns_404(client: TestClient) -> None:
    assert client.get("/api/v1/does-not-exist").status_code == 404


def test_other_api_versions_are_not_served(client: TestClient) -> None:
    assert client.get("/api/v2/health").status_code == 404


def test_feature_routers_can_be_attached_under_the_prefix() -> None:
    feature = APIRouter(prefix="/things", tags=["things"])

    @feature.get("")
    async def list_things() -> list[str]:
        return ["a"]

    parent = APIRouter(prefix=API_PREFIX)
    parent.include_router(feature)
    app = create_app(AppSettings(_env_file=None))  # type: ignore[call-arg]
    app.include_router(parent)
    with TestClient(app) as test_client:
        assert test_client.get("/api/v1/things").json() == ["a"]


def test_versioned_routes_get_request_metadata_headers(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert "x-request-id" in response.headers
    assert "x-process-time" in response.headers
