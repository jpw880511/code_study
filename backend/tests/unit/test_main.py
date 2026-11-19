import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from src.config import AppSettings
from src.db import session as session_module
from src.main import create_app

ALLOWED = "http://localhost:5173"
BLOCKED = "http://evil.example.com"


def make_settings(**values: Any) -> AppSettings:
    options: dict[str, Any] = {"_env_file": None, **values}
    return AppSettings(**options)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(make_settings(allowed_origins=[ALLOWED]))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ENVIRONMENT", "DEBUG", "ALLOWED_ORIGINS", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    session_module.get_session_factory.cache_clear()


def test_settings_defaults() -> None:
    settings = make_settings()
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.allowed_origins == [ALLOWED]


def test_settings_parse_comma_separated_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", f"{ALLOWED}, https://app.example.com ,")
    assert make_settings().allowed_origins == [ALLOWED, "https://app.example.com"]


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")
    settings = make_settings()
    assert settings.environment == "production"
    assert settings.debug is True


def test_wildcard_origin_is_rejected() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        make_settings(allowed_origins=["*"])


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_docs_are_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"]


def test_cors_allows_whitelisted_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": ALLOWED})
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_ignores_unknown_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": BLOCKED})
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_for_whitelisted_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": ALLOWED,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert "POST" in response.headers["access-control-allow-methods"]


def test_cors_preflight_rejects_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={"Origin": BLOCKED, "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_request_id_is_generated(client: TestClient) -> None:
    first = client.get("/health").headers["x-request-id"]
    second = client.get("/health").headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert first != second


def test_safe_client_request_id_is_kept(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-abc_123.4"})
    assert response.headers["x-request-id"] == "trace-abc_123.4"


@pytest.mark.parametrize("unsafe", ["has space", "new\tline", "x" * 65, "<script>"])
def test_unsafe_client_request_id_is_replaced(client: TestClient, unsafe: str) -> None:
    response = client.get("/health", headers={"X-Request-ID": unsafe})
    assert response.headers["x-request-id"] != unsafe
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_process_time_header(client: TestClient) -> None:
    value = float(client.get("/health").headers["x-process-time"])
    assert 0 <= value < 3


async def test_dispose_engine_is_noop_when_never_connected() -> None:
    await session_module.dispose_engine()


def test_app_starts_and_stops_without_database_url() -> None:
    with TestClient(create_app(make_settings())) as test_client:
        assert test_client.get("/health").status_code == 200


def test_module_level_app_exists() -> None:
    from src.main import app

    assert app.title
