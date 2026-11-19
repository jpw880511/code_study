import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from src.db import session as session_module
from src.db.session import create_engine, create_session_factory, to_async_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@localhost:5432/db", "postgresql+asyncpg://u:p@localhost:5432/db"),
        ("postgres://u:p@localhost/db", "postgresql+asyncpg://u:p@localhost/db"),
        ("postgresql+asyncpg://u:p@localhost/db", "postgresql+asyncpg://u:p@localhost/db"),
    ],
)
def test_to_async_url(url: str, expected: str) -> None:
    assert to_async_url(url) == expected


def test_to_async_url_rejects_other_databases() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        to_async_url("sqlite:///x.db")


def test_create_engine_uses_asyncpg_driver() -> None:
    engine = create_engine("postgresql://u:p@localhost:5432/db")
    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+asyncpg"


def test_session_factory_does_not_expire_on_commit() -> None:
    engine = create_engine("postgresql://u:p@localhost:5432/db")
    factory = create_session_factory(engine)
    session = factory()
    assert isinstance(session, AsyncSession)
    assert session.sync_session.expire_on_commit is False


def test_get_session_factory_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    session_module.get_session_factory.cache_clear()
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        session_module.get_session_factory()
