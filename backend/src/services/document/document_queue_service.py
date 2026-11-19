"""The waiting line of learning documents and the one place that changes their status.

pending -> in_progress -> completed | failed. Every change is a conditional UPDATE ("only if it
is still in the state I expect"), so two workers, a redelivered job or a late result cannot make
a document twice or overwrite a finished one. The service never commits: the caller does.

Rules (contracts/phase6-document-generation-api.md, section 3):
  - a user has at most 3 documents in progress; the rest wait in pending (start() answers
    DEFERRED and the worker tries again later);
  - an in_progress document older than 15 minutes is failed, whoever notices it first;
  - failure texts are for the learner and never contain an exception, a prompt or code.
"""

import enum
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import LearningDocument, Project, Task
from src.models.learning_document import empty_content
from src.services.document.errors import DocumentNotFoundError

MAX_CONCURRENT_PER_USER = 3
# Longer than the hard time limit of the generation job (600 s), so a live job is never judged.
STALE_AFTER = timedelta(minutes=15)
ACTIVE_STATUSES = ("pending", "in_progress")

STALE_MESSAGE = (
    "문서를 만드는 데 너무 오래 걸려 중단되었습니다. "
    "더 작은 코드 파일로 다시 업로드하거나 고객지원에 문의하세요."
)
TIMEOUT_MESSAGE = (
    "문서를 만드는 시간이 제한을 넘었습니다. "
    "더 작은 코드 파일로 다시 업로드하거나 고객지원에 문의하세요."
)
ENQUEUE_FAILED_MESSAGE = (
    "문서 생성 요청을 접수하지 못했습니다. 잠시 후 다시 시도하거나 고객지원에 문의하세요."
)
UNKNOWN_ERROR_MESSAGE = (
    "문서를 만드는 중 알 수 없는 오류가 발생했습니다. "
    "잠시 후 다시 시도하거나 고객지원에 문의하세요."
)


class StartOutcome(enum.Enum):
    STARTED = "started"  # this caller now owns the document and must generate it
    DEFERRED = "deferred"  # the user is at the limit: stays pending, try again later
    SKIPPED = "skipped"  # nothing to do: done, failed, taken by someone else, or gone


@dataclass(frozen=True)
class DocumentStatus:
    status: str
    generation_started_at: datetime | None
    generation_completed_at: datetime | None
    elapsed_seconds: int | None
    estimated_total_seconds: int | None
    notice: str | None
    error: str | None


def utc_now() -> datetime:
    return datetime.now(UTC)


def estimate_total_seconds(total_lines: int | None) -> int:
    """A rough total time: 13-29 lines took 18-22 s; capped at the 180 s of FR-025."""
    return min(180, max(20, round(15 + 0.25 * (total_lines or 0))))


def _tasks_of(user_id: uuid.UUID) -> Any:
    return (
        select(Task.id)
        .join(Project, Task.project_id == Project.id)
        .where(Project.user_id == user_id)
    )


class DocumentQueueService:
    def __init__(self, session: AsyncSession, *, clock: Callable[[], datetime] = utc_now) -> None:
        self.session = session
        self._clock = clock

    async def register(self, task_id: uuid.UUID) -> LearningDocument:
        """The pending document of a new task, with the id its job will be sent under."""
        document = LearningDocument(
            task_id=task_id,
            content=empty_content(),
            generation_status="pending",
            celery_task_id=str(uuid.uuid4()),
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def get(self, task_id: uuid.UUID) -> LearningDocument:
        """The task's document, after failing it if it has been running for too long."""
        await self._expire_stale(LearningDocument.task_id == task_id)
        document = (
            await self.session.execute(
                select(LearningDocument)
                .where(LearningDocument.task_id == task_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError()
        return document

    async def owner_id(self, task_id: uuid.UUID) -> uuid.UUID | None:
        """The user whose project holds the task, or None when it is gone."""
        owner: uuid.UUID | None = (
            await self.session.execute(
                select(Project.user_id)
                .join(Task, Task.project_id == Project.id)
                .where(Task.id == task_id)
            )
        ).scalar_one_or_none()
        return owner

    async def start(self, task_id: uuid.UUID) -> StartOutcome:
        """pending -> in_progress for exactly one caller, unless the user is at the limit."""
        user_id = await self.owner_id(task_id)
        if user_id is None:
            return StartOutcome.SKIPPED
        # One start per user at a time, so that counting and then claiming cannot let four
        # workers each see "two running". Released when the caller commits.
        await self.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(str(user_id), 0)))
        )
        await self._expire_stale(LearningDocument.task_id.in_(_tasks_of(user_id)))
        status = (
            await self.session.execute(
                select(LearningDocument.generation_status).where(
                    LearningDocument.task_id == task_id
                )
            )
        ).scalar_one_or_none()
        if status != "pending":
            return StartOutcome.SKIPPED
        running = (
            await self.session.execute(
                select(func.count())
                .select_from(LearningDocument)
                .where(
                    LearningDocument.generation_status == "in_progress",
                    LearningDocument.task_id.in_(_tasks_of(user_id)),
                )
            )
        ).scalar_one()
        if running >= MAX_CONCURRENT_PER_USER:
            return StartOutcome.DEFERRED
        claimed = await self._transition(
            task_id,
            ("pending",),
            generation_status="in_progress",
            generation_started_at=self._clock(),
            generation_completed_at=None,
            generation_error=None,
        )
        return StartOutcome.STARTED if claimed else StartOutcome.SKIPPED

    async def complete(self, task_id: uuid.UUID, content: dict[str, Any]) -> bool:
        """Store the finished document. False if it is no longer in progress (nothing changes)."""
        return await self._transition(
            task_id,
            ("in_progress",),
            generation_status="completed",
            content=content,
            generation_completed_at=self._clock(),
            generation_error=None,
        )

    async def fail(self, task_id: uuid.UUID, message: str) -> bool:
        """The generation failed. `message` is for the learner. False if it is not in progress."""
        return await self._transition(
            task_id,
            ("in_progress",),
            generation_status="failed",
            generation_completed_at=self._clock(),
            generation_error=message,
        )

    async def fail_unsent(self, task_id: uuid.UUID, message: str) -> bool:
        """The job never reached the queue. Only a document still pending can fail this way."""
        return await self._transition(
            task_id,
            ("pending",),
            generation_status="failed",
            generation_completed_at=self._clock(),
            generation_error=message,
        )

    def describe(
        self, task: Task, document: LearningDocument, notice: str | None
    ) -> DocumentStatus:
        """The answer of the status endpoint. Elapsed time is measured here, on the server."""
        status = document.generation_status or "pending"
        active = status in ACTIVE_STATUSES
        started = document.generation_started_at
        elapsed = None
        if status == "in_progress" and started is not None:
            elapsed = max(0, int((self._clock() - started).total_seconds()))
        lines = task.uploaded_code.total_lines if task.uploaded_code else None
        return DocumentStatus(
            status=status,
            generation_started_at=started,
            generation_completed_at=document.generation_completed_at,
            elapsed_seconds=elapsed,
            estimated_total_seconds=estimate_total_seconds(lines) if active else None,
            notice=notice if active else None,
            error=document.generation_error if status == "failed" else None,
        )

    async def _transition(
        self, task_id: uuid.UUID, from_statuses: tuple[str, ...], **values: Any
    ) -> bool:
        changed = (
            await self.session.execute(
                update(LearningDocument)
                .where(
                    LearningDocument.task_id == task_id,
                    LearningDocument.generation_status.in_(from_statuses),
                )
                .values(**values)
                .returning(LearningDocument.id)
                .execution_options(synchronize_session=False)
            )
        ).first()
        return changed is not None

    async def _expire_stale(self, *conditions: Any) -> None:
        now = self._clock()
        await self.session.execute(
            update(LearningDocument)
            .where(
                LearningDocument.generation_status == "in_progress",
                LearningDocument.generation_started_at < now - STALE_AFTER,
                *conditions,
            )
            .values(
                generation_status="failed",
                generation_completed_at=now,
                generation_error=STALE_MESSAGE,
            )
            .execution_options(synchronize_session=False)
        )
