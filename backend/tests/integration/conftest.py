"""Fixtures for tests that need data committed for real (other sessions or the worker read it)."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.db import session as session_module
from src.db.session import create_engine, create_session_factory
from src.models import User


@pytest.fixture
async def committed_factory(
    test_database_url: str, migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A session factory on the test database; the app's get_session uses it too.

    Everything the test commits is removed afterwards (users cascade to the rest).
    """
    engine = create_engine(test_database_url)
    created = create_session_factory(engine)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: created)
    yield created
    async with created() as cleanup:
        await cleanup.execute(delete(User))
        await cleanup.commit()
    await engine.dispose()
