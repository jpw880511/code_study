import logging
import threading
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.api.dependencies import get_document_dispatcher
from src.models import LearningDocument, Task
from src.services.document.document_dispatcher import DocumentDispatcher
from src.services.document.document_queue_service import (
    ENQUEUE_FAILED_MESSAGE,
    DocumentQueueService,
)
from src.tasks import document_generation
from tests.queue_helpers import make_user, upload_task

SECRET = "redis://:hunter2-password@broker:6379/0"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


async def committed_task(factory: async_sessionmaker[AsyncSession], root: Path) -> Task:
    async with factory() as db:
        task = await upload_task(db, root, await make_user(db))
        await db.commit()
    return task


async def document_of(factory: async_sessionmaker[AsyncSession], task: Task) -> LearningDocument:
    async with factory() as db:
        return (
            await db.execute(select(LearningDocument).where(LearningDocument.task_id == task.id))
        ).scalar_one()


async def test_dispatch_sends_the_job_off_the_event_loop(
    committed_factory: async_sessionmaker[AsyncSession], root: Path
) -> None:
    task = await committed_task(committed_factory, root)
    seen: list[tuple[str, str, int]] = []

    def send(task_id: str, job_id: str) -> None:
        seen.append((task_id, job_id, threading.get_ident()))

    dispatcher = DocumentDispatcher(send, lambda: committed_factory)
    await dispatcher.dispatch(task.id, "job-1")
    assert [(a, b) for a, b, _ in seen] == [(str(task.id), "job-1")]
    assert seen[0][2] != threading.get_ident()  # a blocking broker call must not stall the loop
    assert (await document_of(committed_factory, task)).generation_status == "pending"


async def test_a_broker_failure_fails_the_document_without_leaking_the_cause(
    committed_factory: async_sessionmaker[AsyncSession],
    root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    task = await committed_task(committed_factory, root)

    def send(task_id: str, job_id: str) -> None:
        raise ConnectionError(f"cannot reach {SECRET}")

    caplog.set_level(logging.DEBUG)
    await DocumentDispatcher(send, lambda: committed_factory).dispatch(task.id, "job-1")
    document = await document_of(committed_factory, task)
    assert document.generation_status == "failed"
    assert document.generation_error == ENQUEUE_FAILED_MESSAGE
    assert document.generation_completed_at is not None
    assert "hunter2" not in caplog.text
    assert "ConnectionError" in caplog.text
    assert str(task.id) in caplog.text


async def test_a_broker_failure_does_not_touch_a_document_a_worker_already_took(
    committed_factory: async_sessionmaker[AsyncSession], root: Path
) -> None:
    task = await committed_task(committed_factory, root)
    async with committed_factory() as db:
        await DocumentQueueService(db).start(task.id)
        await db.commit()

    def send(task_id: str, job_id: str) -> None:
        raise ConnectionError("late")

    await DocumentDispatcher(send, lambda: committed_factory).dispatch(task.id, "job-1")
    assert (await document_of(committed_factory, task)).generation_status == "in_progress"


async def test_dispatch_never_raises_even_if_the_failure_cannot_be_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def send(task_id: str, job_id: str) -> None:
        raise ConnectionError(SECRET)

    def no_database() -> Any:
        raise RuntimeError(f"database down {SECRET}")

    caplog.set_level(logging.DEBUG)
    await DocumentDispatcher(send, no_database).dispatch(uuid.uuid4(), "job-1")
    assert "hunter2" not in caplog.text
    assert "RuntimeError" in caplog.text


async def test_the_default_dispatcher_uses_the_modules_sender_and_the_app_database(
    committed_factory: async_sessionmaker[AsyncSession],
    root: Path,
    sent_jobs: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await committed_task(committed_factory, root)
    await get_document_dispatcher().dispatch(task.id, "job-1")
    assert sent_jobs == [(str(task.id), "job-1")]

    def broken(task_id: str, job_id: str) -> None:
        raise ConnectionError("down")

    monkeypatch.setattr(document_generation, "enqueue_generation", broken)
    await get_document_dispatcher().dispatch(task.id, "job-2")
    assert (await document_of(committed_factory, task)).generation_status == "failed"
