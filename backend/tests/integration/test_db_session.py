from collections.abc import AsyncGenerator, AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.db import session as session_module

EMAIL = "session-test@example.com"


@pytest.fixture
async def configured_session(
    monkeypatch: pytest.MonkeyPatch, test_database_url: str, migrated_engine: object
) -> AsyncIterator[None]:
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    session_module.get_session_factory.cache_clear()
    yield
    await session_module.dispose_engine()


async def _drain(generator: AsyncGenerator[AsyncSession, None]) -> AsyncSession:
    return await generator.__anext__()


@pytest.mark.usefixtures("configured_session")
async def test_get_session_yields_working_session() -> None:
    generator = session_module.get_session()
    session = await _drain(generator)
    assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
    await generator.aclose()


@pytest.mark.usefixtures("configured_session")
async def test_get_session_commits_on_success() -> None:
    generator = session_module.get_session()
    session = await _drain(generator)
    await session.execute(
        text("INSERT INTO users (email, password_hash) VALUES (:e, 'h')"), {"e": EMAIL}
    )
    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()

    verify = session_module.get_session_factory()()
    async with verify:
        count = (
            await verify.execute(text("SELECT count(*) FROM users WHERE email = :e"), {"e": EMAIL})
        ).scalar_one()
        assert count == 1
        await verify.execute(text("DELETE FROM users WHERE email = :e"), {"e": EMAIL})
        await verify.commit()


@pytest.mark.usefixtures("configured_session")
async def test_get_session_rolls_back_on_error() -> None:
    generator = session_module.get_session()
    session = await _drain(generator)
    await session.execute(
        text("INSERT INTO users (email, password_hash) VALUES (:e, 'h')"), {"e": EMAIL}
    )
    with pytest.raises(RuntimeError, match="boom"):
        await generator.athrow(RuntimeError("boom"))

    verify = session_module.get_session_factory()()
    async with verify:
        count = (
            await verify.execute(text("SELECT count(*) FROM users WHERE email = :e"), {"e": EMAIL})
        ).scalar_one()
        assert count == 0
