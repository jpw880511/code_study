from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.db.config import get_database_settings

ASYNC_DRIVER = "postgresql+asyncpg"


def to_async_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.get_backend_name() not in ("postgresql", "postgres"):
        raise ValueError("Only PostgreSQL database URLs are supported")
    return parsed.set(drivername=ASYNC_DRIVER).render_as_string(hide_password=False)


def create_engine(url: str, **engine_options: Any) -> AsyncEngine:
    return create_async_engine(to_async_url(url), **engine_options)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    settings = get_database_settings()
    return create_session_factory(create_engine(settings.database_url, **settings.engine_options))


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request, committed on success, rolled back on error."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    if get_session_factory.cache_info().currsize == 0:
        return
    factory = get_session_factory()
    get_session_factory.cache_clear()
    await factory.kw["bind"].dispose()
