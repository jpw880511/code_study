"""Hands a committed task's document job to the queue, and records it when that is impossible.

It runs after the request has committed (the endpoint adds it as a background task, which
FastAPI only starts once the response is going out, so never after a rollback). A worker that
receives the message therefore always finds the task and its pending document.

Failing to reach the broker must not undo the upload: the document is marked failed with a
learner-facing text, and the cause (only its kind) goes to the server log.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.services.document.document_queue_service import (
    ENQUEUE_FAILED_MESSAGE,
    DocumentQueueService,
)

logger = logging.getLogger(__name__)


class DocumentDispatcher:
    def __init__(
        self,
        send: Callable[[str, str], None],
        session_factory: Callable[[], async_sessionmaker[AsyncSession]],
    ) -> None:
        self._send = send  # (task id, job id): blocking, so it runs in a thread
        self._session_factory = session_factory

    async def dispatch(self, task_id: uuid.UUID, job_id: str) -> None:
        """Send the job. Never raises: the request that asked for it is already answered."""
        try:
            await asyncio.to_thread(self._send, str(task_id), job_id)
            return
        except Exception as exc:
            logger.error(
                "Could not queue document generation: task=%s kind=%s",
                task_id,
                type(exc).__name__,
            )
        try:
            async with self._session_factory()() as session:
                await DocumentQueueService(session).fail_unsent(task_id, ENQUEUE_FAILED_MESSAGE)
                await session.commit()
        except Exception as exc:
            logger.error(
                "Could not record the failed queueing: task=%s kind=%s", task_id, type(exc).__name__
            )
