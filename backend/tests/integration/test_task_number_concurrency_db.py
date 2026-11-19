"""Task numbers under real concurrency: separate connections, real commits.

The other database tests share one rolled-back transaction, which cannot show a race. These
tests commit for real, so they clean up after themselves by deleting the user (cascade).
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from src.db.session import create_engine, create_session_factory
from src.models import User
from src.services.project_service import ProjectService
from src.services.task_service import TaskService


@dataclass
class Setup:
    factory: async_sessionmaker
    user_id: uuid.UUID
    project_id: uuid.UUID


@pytest.fixture
async def setup(test_database_url: str, migrated_engine: Engine) -> AsyncIterator[Setup]:
    engine: AsyncEngine = create_engine(test_database_url)
    factory = create_session_factory(engine)
    async with factory() as session:
        user = User(email=f"race-{uuid.uuid4().hex}@example.com", password_hash="$2b$12$hash")
        session.add(user)
        await session.flush()
        project = await ProjectService(session).create(user.id, "동시 생성")
        await session.commit()
        user_id, project_id = user.id, project.id
    yield Setup(factory, user_id, project_id)
    async with factory() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
    await engine.dispose()


async def create_and_commit(setup: Setup, title: str) -> int:
    async with setup.factory() as session:
        task = await TaskService(session).create(setup.user_id, setup.project_id, title)
        number = task.task_number
        await session.commit()
        return number


async def test_many_connections_creating_at_once_get_distinct_consecutive_numbers(
    setup: Setup,
) -> None:
    numbers = await asyncio.gather(
        *(create_and_commit(setup, f"동시에 만든 태스크 {i}") for i in range(8))
    )

    assert sorted(numbers) == list(range(1, 9))


async def test_a_second_creator_waits_for_the_first_to_commit(setup: Setup) -> None:
    """The project row lock is what serialises them: without it both would compute number 1."""
    async with setup.factory() as first:
        holder = await TaskService(first).create(
            setup.user_id, setup.project_id, "먼저 만든 태스크"
        )
        assert holder.task_number == 1  # created, not yet committed: the lock is held

        waiting = asyncio.create_task(create_and_commit(setup, "기다리는 태스크"))
        done, _ = await asyncio.wait({waiting}, timeout=0.5)
        assert not done  # blocked on the project row

        await first.commit()

    assert await asyncio.wait_for(waiting, timeout=10) == 2
