from typing import Any

import pytest
from pydantic import ValidationError
from src.db.config import DatabaseSettings, get_database_settings
from src.db.session import create_engine

URL = "postgresql://u:p@localhost:5432/db"


def make_settings(**values: Any) -> DatabaseSettings:
    """Build settings from explicit values only, ignoring any real .env file."""
    options: dict[str, Any] = {"_env_file": None, **values}
    return DatabaseSettings(**options)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DATABASE_URL",
        "DB_POOL_SIZE",
        "DB_MAX_OVERFLOW",
        "DB_POOL_TIMEOUT",
        "DB_POOL_RECYCLE",
        "DB_POOL_PRE_PING",
        "DB_ECHO",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    settings = make_settings(database_url=URL)
    assert settings.pool_size == 5
    assert settings.max_overflow == 10
    assert settings.pool_timeout == 30
    assert settings.pool_recycle == 1800
    assert settings.pool_pre_ping is True
    assert settings.echo is False


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("DB_POOL_SIZE", "20")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "0")
    monkeypatch.setenv("DB_POOL_PRE_PING", "false")
    settings = make_settings()
    assert settings.database_url == URL
    assert settings.pool_size == 20
    assert settings.max_overflow == 0
    assert settings.pool_pre_ping is False


def test_ignores_unrelated_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    assert make_settings(database_url=URL).database_url == URL


@pytest.mark.parametrize(
    "overrides",
    [{"pool_size": 0}, {"max_overflow": -1}, {"pool_timeout": 0}, {"pool_recycle": -5}],
)
def test_rejects_invalid_pool_values(overrides: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url=URL, **overrides)


def test_engine_options() -> None:
    settings = make_settings(database_url=URL, pool_size=7)
    assert settings.engine_options == {
        "pool_size": 7,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
        "echo": False,
    }


def test_get_database_settings_requires_database_url() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_database_settings()


def test_get_database_settings_reads_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", URL)
    assert get_database_settings().database_url == URL


def test_engine_receives_pool_configuration() -> None:
    settings = make_settings(database_url=URL, pool_size=3, max_overflow=2)
    engine = create_engine(settings.database_url, **settings.engine_options)
    pool = engine.sync_engine.pool
    assert pool.size() == 3  # type: ignore[attr-defined]
    assert pool._max_overflow == 2  # type: ignore[attr-defined]
