"""The synchronous entry point of the Celery job: one fresh engine per run, closed afterwards.

These tests are plain functions on purpose: the job calls asyncio.run, which cannot be nested
inside a running event loop.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncEngine
from src.db import session as session_module
from src.db.session import create_engine, create_session_factory
from src.services.ai.gemini_client import GeminiResponse
from src.services.document.document_notice_store import NoticeStore
from src.tasks import document_generation
from src.tasks.document_generation import COMPLETED, run_generate_document
from tests.document_fixtures import valid_doc
from tests.queue_helpers import MemoryRedis, make_user, upload_task


class FakeClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **options: Any) -> GeminiResponse:
        self.prompts.append(prompt)
        return GeminiResponse(
            text=json.dumps(valid_doc(), ensure_ascii=False), model="fake", prompt_tokens=1,
            completion_tokens=1, thinking_tokens=0, finish_reason="STOP",
        )  # fmt: skip


@pytest.fixture
def worker_env(
    monkeypatch: pytest.MonkeyPatch, test_database_url: str, migrated_engine: Engine, tmp_path: Path
) -> Path:
    root = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("UPLOAD_STORAGE_PATH", str(root))
    return root


def seed(test_database_url: str, root: Path, count: int) -> list[Any]:
    async def go() -> list[Any]:
        engine = create_engine(test_database_url)
        try:
            async with create_session_factory(engine)() as db:
                user = await make_user(db)
                ids = [(await upload_task(db, root, user)).id for _ in range(count)]
                await db.commit()
                return ids
        finally:
            await engine.dispose()

    return asyncio.run(go())


@pytest.fixture(autouse=True)
def clean_users(migrated_engine: Engine) -> Any:
    yield
    with migrated_engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))


def statuses(migrated_engine: Engine) -> list[str]:
    with migrated_engine.connect() as connection:
        rows = connection.execute(
            text("SELECT generation_status FROM learning_documents ORDER BY created_at")
        )
        return [row[0] for row in rows]


def test_each_run_builds_and_disposes_its_own_engine_on_its_own_event_loop(
    monkeypatch: pytest.MonkeyPatch,
    worker_env: Path,
    test_database_url: str,
    migrated_engine: Engine,
) -> None:
    ids = seed(test_database_url, worker_env, 2)
    created: list[AsyncEngine] = []
    disposed: list[AsyncEngine] = []
    original_dispose = AsyncEngine.dispose

    def spy_create_engine(url: str, **options: Any) -> AsyncEngine:
        engine = create_engine(url, **options)
        created.append(engine)
        return engine

    async def spy_dispose(self: AsyncEngine, *args: Any, **kwargs: Any) -> None:
        disposed.append(self)
        await original_dispose(self, *args, **kwargs)

    monkeypatch.setattr(document_generation, "create_engine", spy_create_engine)
    monkeypatch.setattr(AsyncEngine, "dispose", spy_dispose)
    client, notices = FakeClient(), NoticeStore(MemoryRedis())
    # Two runs in a row, each in its own asyncio.run: a shared engine would break the second.
    assert run_generate_document(str(ids[0]), client=client, notices=notices) == COMPLETED  # type: ignore[arg-type]
    assert run_generate_document(str(ids[1]), client=client, notices=notices) == COMPLETED  # type: ignore[arg-type]
    assert len(created) == 2 and created[0] is not created[1]
    assert disposed == created
    assert session_module.get_session_factory.cache_info().currsize == 0  # the cached one is unused
    assert statuses(migrated_engine) == ["completed", "completed"]
    assert len(client.prompts) == 2


def test_the_engine_is_disposed_even_when_the_job_breaks(
    monkeypatch: pytest.MonkeyPatch, worker_env: Path, test_database_url: str
) -> None:
    ids = seed(test_database_url, worker_env, 1)
    disposed: list[bool] = []
    original_dispose = AsyncEngine.dispose

    async def spy_dispose(self: AsyncEngine, *args: Any, **kwargs: Any) -> None:
        disposed.append(True)
        await original_dispose(self, *args, **kwargs)

    monkeypatch.setattr(AsyncEngine, "dispose", spy_dispose)

    async def broken(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("worker bug")

    monkeypatch.setattr(document_generation, "generate_for_task", broken)
    with pytest.raises(RuntimeError, match="worker bug"):
        run_generate_document(str(ids[0]), client=FakeClient(), notices=NoticeStore(None))  # type: ignore[arg-type]
    assert disposed == [True]


def test_without_injection_it_builds_the_real_client_and_a_lazy_redis_store(
    monkeypatch: pytest.MonkeyPatch,
    worker_env: Path,
    test_database_url: str,
    migrated_engine: Engine,
) -> None:
    """No API key in the tests: the real client refuses at once, and nothing goes out."""
    ids = seed(test_database_url, worker_env, 1)
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # nobody listens: notices stay quiet
    assert run_generate_document(str(ids[0])) == document_generation.FAILED
    with migrated_engine.connect() as connection:
        error = connection.execute(text("SELECT generation_error FROM learning_documents")).scalar()
    assert error == "AI 서비스가 설정되지 않았습니다. 관리자에게 문의하세요."


class ClosableClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.closed = 0

    async def aclose(self) -> None:
        self.closed += 1


def test_the_client_the_job_made_is_closed_before_its_event_loop_ends(
    monkeypatch: pytest.MonkeyPatch, worker_env: Path, test_database_url: str
) -> None:
    """An open SDK connection closed after the loop has ended logs "Event loop is closed"."""
    ids = seed(test_database_url, worker_env, 1)
    made: list[ClosableClient] = []

    def make() -> ClosableClient:
        made.append(ClosableClient())
        return made[0]

    monkeypatch.setattr(document_generation, "GeminiClient", make)
    assert run_generate_document(str(ids[0]), notices=NoticeStore(MemoryRedis())) == COMPLETED  # type: ignore[arg-type]
    assert [client.closed for client in made] == [1]


def test_the_client_is_closed_even_when_the_job_breaks(
    monkeypatch: pytest.MonkeyPatch, worker_env: Path, test_database_url: str
) -> None:
    ids = seed(test_database_url, worker_env, 1)
    made: list[ClosableClient] = []

    def make() -> ClosableClient:
        made.append(ClosableClient())
        return made[0]

    async def broken(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("worker bug")

    monkeypatch.setattr(document_generation, "GeminiClient", make)
    monkeypatch.setattr(document_generation, "generate_for_task", broken)
    with pytest.raises(RuntimeError, match="worker bug"):
        run_generate_document(str(ids[0]), notices=NoticeStore(None))
    assert [client.closed for client in made] == [1]


def test_a_client_handed_in_by_the_caller_is_left_open(
    worker_env: Path, test_database_url: str
) -> None:
    ids = seed(test_database_url, worker_env, 1)
    client = ClosableClient()
    assert (
        run_generate_document(str(ids[0]), client=client, notices=NoticeStore(MemoryRedis()))
        == COMPLETED
    )  # type: ignore[arg-type]
    assert client.closed == 0  # whoever made it closes it
