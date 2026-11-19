"""The Celery job that writes a task's learning document.

Celery jobs are plain functions, the document service is async, so the job runs it with
asyncio.run. Each run builds its own database engine and closes it at the end: the cached
session factory of the web app is bound to the event loop that first used it, and every
asyncio.run starts a new loop.

Delivery is "at least once" (acks_late, and a job lost with its worker is delivered again), so
running the same job twice must be harmless: DocumentQueueService.start() lets only one run
claim a pending document, and a finished one is never claimed again.

Logs name the task, the kind of error and an upstream status code. They never contain the
exception text, the prompt or the code (they may carry the learner's code).
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import AppSettings
from src.db.config import get_database_settings
from src.db.session import create_engine, create_session_factory
from src.services.ai.gemini_client import GeminiClient
from src.services.ai.prompts import PromptFile
from src.services.code_analysis.code_upload_service import CodeUploadService
from src.services.code_analysis.file_storage import FileStorage
from src.services.document.document_generation_service import (
    DocumentGenerationService,
    RetryEvent,
)
from src.services.document.document_notice_store import NoticeStore, notice_text
from src.services.document.document_queue_service import (
    TIMEOUT_MESSAGE,
    UNKNOWN_ERROR_MESSAGE,
    DocumentQueueService,
    StartOutcome,
    utc_now,
)
from src.services.errors import DomainError
from src.services.task_errors import TaskNotFoundError
from src.services.task_service import TaskService
from src.tasks.celery_app import RedisSettings, celery_app

logger = logging.getLogger(__name__)

QUEUE = "document_generation"
DEFER_SECONDS = 15  # how long a document waits for a free slot before the next look

# What a run did, for the job's result and for the tests.
COMPLETED = "completed"
FAILED = "failed"
SKIPPED = "skipped"  # nothing to do (done, taken by another run, or gone)
DEFERRED = "deferred"  # the user is at the limit of 3: try again in DEFER_SECONDS


def enqueue_generation(task_id: str, job_id: str) -> None:
    """Send the job to the broker under the id already stored in the document row.

    Blocking, and short on patience: a broker that is down must fail fast (the document then
    becomes failed) instead of holding the caller.
    """
    generate_document.apply_async(
        args=[task_id],
        task_id=job_id,
        queue=QUEUE,
        retry=True,
        retry_policy={"max_retries": 1, "interval_start": 0, "interval_step": 0.2},
    )


async def _read_files(
    session: AsyncSession, storage: FileStorage, queue: DocumentQueueService, task_id: uuid.UUID
) -> tuple[list[PromptFile], str, str]:
    user_id = await queue.owner_id(task_id)
    if user_id is None:  # the task was deleted for good while the job waited
        raise TaskNotFoundError()
    task = await TaskService(session).get(user_id, task_id)  # ownership and trash rules
    stored = await CodeUploadService(session, storage).read_code(user_id, task_id)
    upload = task.uploaded_code
    files = [
        PromptFile(s.file.file_path or s.file.file_name, s.content, s.language) for s in stored
    ]
    language = (upload.detected_language if upload else None) or "unknown"
    level = (upload.complexity_level if upload else None) or "beginner"
    return files, language, level


def _log_failure(task_id: uuid.UUID, exc: BaseException) -> None:
    logger.error(
        "Document generation failed: task=%s kind=%s status=%s",
        task_id,
        type(exc).__name__,
        getattr(exc, "status_code", None),
    )


async def generate_for_task(
    task_id: uuid.UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    storage: FileStorage,
    client: GeminiClient,
    notices: NoticeStore,
    clock: Callable[[], datetime] = utc_now,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> str:
    """Claim the task's document, write it and store the result. Returns what was done."""
    async with session_factory() as session:
        outcome = await DocumentQueueService(session, clock=clock).start(task_id)
        await session.commit()  # also ends the per-user lock
    if outcome is StartOutcome.DEFERRED:
        return DEFERRED
    if outcome is StartOutcome.SKIPPED:
        return SKIPPED

    async def on_retry(event: RetryEvent) -> None:
        await notices.set(task_id, notice_text(event))

    message: str
    try:
        async with session_factory() as session:
            files, language, level = await _read_files(
                session, storage, DocumentQueueService(session, clock=clock), task_id
            )
        service = DocumentGenerationService(client, sleep=sleep, on_retry=on_retry)
        generated = await service.generate(files, language=language, complexity_level=level)
    except SoftTimeLimitExceeded as exc:
        _log_failure(task_id, exc)
        message = TIMEOUT_MESSAGE
    except DomainError as exc:  # its message is written for the learner
        _log_failure(task_id, exc)
        message = exc.message
    except Exception as exc:
        _log_failure(task_id, exc)
        message = UNKNOWN_ERROR_MESSAGE
    else:
        logger.info(
            "Document generated: task=%s model=%s calls=%s tokens=%s/%s/%s",
            task_id,
            generated.model,
            generated.model_calls,
            generated.prompt_tokens,
            generated.completion_tokens,
            generated.thinking_tokens,
        )
        async with session_factory() as session:
            stored = await DocumentQueueService(session, clock=clock).complete(
                task_id, generated.content
            )
            await session.commit()
        await notices.clear(task_id)
        return COMPLETED if stored else SKIPPED  # SKIPPED: failed as stale in the meantime

    async with session_factory() as session:
        await DocumentQueueService(session, clock=clock).fail(task_id, message)
        await session.commit()
    await notices.clear(task_id)
    return FAILED


async def _run(
    task_id: uuid.UUID,
    client: GeminiClient | None,
    notices: NoticeStore | None,
    sleep: Callable[[float], Awaitable[None]],
) -> str:
    settings = get_database_settings()
    engine = create_engine(settings.database_url, **settings.engine_options)
    store = notices if notices is not None else NoticeStore.from_url(RedisSettings().redis_url)
    try:
        llm = client if client is not None else GeminiClient()
        try:
            return await generate_for_task(
                task_id,
                session_factory=create_session_factory(engine),
                storage=FileStorage(AppSettings().upload_storage_path),
                client=llm,
                notices=store,
                sleep=sleep,
            )
        finally:
            if client is None:
                # Its connections must be closed while this job's event loop still runs.
                await llm.aclose()
    finally:
        await engine.dispose()
        if notices is None:
            await store.aclose()


def run_generate_document(
    task_id: str,
    *,
    client: GeminiClient | None = None,
    notices: NoticeStore | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> str:
    """The synchronous body of the job. `client` and `notices` are for tests."""
    return asyncio.run(_run(uuid.UUID(task_id), client, notices, sleep))


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="document_generation.generate",
    queue=QUEUE,
    acks_late=True,  # a job lost with its worker is delivered again ...
    reject_on_worker_lost=True,  # ... and start() makes the repeat harmless
    # Longer than the global 300 s: three busy-service retries with their waits and two quality
    # retries can add up. The document is judged stale only after 15 minutes (> hard limit).
    soft_time_limit=540,
    time_limit=600,
)
def generate_document(self: Any, task_id: str) -> str:
    outcome = run_generate_document(task_id)
    if outcome == DEFERRED:
        raise self.retry(countdown=DEFER_SECONDS, max_retries=None)
    return outcome
