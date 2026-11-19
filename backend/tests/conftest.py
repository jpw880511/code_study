import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import AppSettings
from src.db.config import DatabaseSettings
from src.db.session import create_engine as create_app_engine
from src.services.ai.config import GeminiSettings
from src.tasks.celery_app import RedisSettings
from src.utils.jwt import JWTSettings

ADMIN_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
TEST_DB_NAME = "codelearning_test"
BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def ignore_dotenv_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not depend on a developer's local .env: settings read only the environment."""
    for settings_class in (
        AppSettings,
        DatabaseSettings,
        GeminiSettings,
        JWTSettings,
        RedisSettings,
    ):
        monkeypatch.setitem(settings_class.model_config, "env_file", None)
    # alembic/env.py calls load_dotenv(), so once a DB test has run the developer's real .env
    # values sit in os.environ. The AI settings must never reach a test that way: a leaked real
    # key would let a unit test call the real Gemini API.
    for name in ("GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)


def alembic_config(database_url: str) -> Config:
    os.environ["DATABASE_URL"] = database_url
    return Config(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    """Create a throwaway database so tests never touch the development data."""
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    except Exception as exc:
        pytest.skip(f"PostgreSQL is not reachable: {exc}")
    url = make_url(ADMIN_URL).set(database=TEST_DB_NAME).render_as_string(hide_password=False)
    yield url
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="session")
def migrated_engine(test_database_url: str) -> Iterator[Engine]:
    config = alembic_config(test_database_url)
    command.upgrade(config, "head")
    engine = create_engine(test_database_url)
    yield engine
    engine.dispose()
    command.downgrade(config, "base")


@pytest.fixture
async def session(test_database_url: str, migrated_engine: Engine) -> AsyncIterator[AsyncSession]:
    """A session whose work (including commits) is rolled back at the end of the test."""
    engine = create_app_engine(test_database_url)
    async with engine.connect() as connection:
        outer = await connection.begin()
        db_session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        yield db_session
        await db_session.close()
        await outer.rollback()
    await engine.dispose()


@pytest.fixture(autouse=True)
def sent_jobs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Uploading a task queues its document; no test may reach a real broker.

    The jobs that would have been sent are collected here as (task id, job id).
    """
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "src.tasks.document_generation.enqueue_generation",
        lambda task_id, job_id: sent.append((task_id, job_id)),
    )
    return sent
