import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import LearningDocument, Task
from src.models.learning_document import empty_content
from src.services.document.document_queue_service import (
    MAX_CONCURRENT_PER_USER,
    STALE_AFTER,
    STALE_MESSAGE,
    DocumentQueueService,
    StartOutcome,
)
from src.services.document.errors import DocumentNotFoundError
from src.services.task_service import TaskService
from tests.document_fixtures import valid_doc
from tests.queue_helpers import make_user, upload_task

NOW = datetime(2026, 11, 18, 9, 0, 0, tzinfo=UTC)


def clock_at(moment: datetime) -> Callable[[], datetime]:
    return lambda: moment


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


async def document_of(session: AsyncSession, task: Task) -> LearningDocument:
    return (
        await session.execute(
            select(LearningDocument)
            .where(LearningDocument.task_id == task.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


async def set_state(
    session: AsyncSession, task: Task, status: str, started_at: datetime | None = None
) -> None:
    await session.execute(
        update(LearningDocument)
        .where(LearningDocument.task_id == task.id)
        .values(generation_status=status, generation_started_at=started_at)
    )


async def test_upload_registers_a_pending_document_with_a_job_id(
    session: AsyncSession, root: Path
) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    document = await document_of(session, task)
    assert document.generation_status == "pending"
    assert document.content == empty_content()
    assert document.generation_started_at is None
    assert document.celery_task_id is not None
    uuid.UUID(document.celery_task_id)  # a UUID the dispatcher sends the job under


async def test_every_document_gets_its_own_job_id(session: AsyncSession, root: Path) -> None:
    user = await make_user(session)
    first = await document_of(session, await upload_task(session, root, user))
    second = await document_of(session, await upload_task(session, root, user))
    assert first.celery_task_id != second.celery_task_id


async def test_start_moves_pending_to_in_progress_once(session: AsyncSession, root: Path) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    assert await queue.start(task.id) is StartOutcome.STARTED
    document = await document_of(session, task)
    assert document.generation_status == "in_progress"
    assert document.generation_started_at == NOW
    assert document.generation_completed_at is None
    assert await queue.start(task.id) is StartOutcome.SKIPPED  # a second delivery


@pytest.mark.parametrize("status", ["completed", "failed", "in_progress"])
async def test_start_skips_documents_that_are_not_pending(
    session: AsyncSession, root: Path, status: str
) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    await set_state(session, task, status, NOW)
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    assert await queue.start(task.id) is StartOutcome.SKIPPED
    assert (await document_of(session, task)).generation_status == status


async def test_start_of_a_task_without_document_is_skipped(session: AsyncSession) -> None:
    queue = DocumentQueueService(session)
    assert await queue.start(uuid.uuid4()) is StartOutcome.SKIPPED


async def test_start_defers_when_the_user_already_runs_three(
    session: AsyncSession, root: Path
) -> None:
    assert MAX_CONCURRENT_PER_USER == 3
    user = await make_user(session)
    tasks = [await upload_task(session, root, user) for _ in range(4)]
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    for task in tasks[:3]:
        assert await queue.start(task.id) is StartOutcome.STARTED
    assert await queue.start(tasks[3].id) is StartOutcome.DEFERRED
    assert (await document_of(session, tasks[3])).generation_status == "pending"
    assert await queue.complete(tasks[0].id, valid_doc())  # a slot frees up
    assert await queue.start(tasks[3].id) is StartOutcome.STARTED


async def test_other_users_documents_do_not_count_against_the_limit(
    session: AsyncSession, root: Path
) -> None:
    busy = await make_user(session, "busy@example.com")
    free = await make_user(session, "free@example.com")
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    for _ in range(3):
        task = await upload_task(session, root, busy)
        assert await queue.start(task.id) is StartOutcome.STARTED
    mine = await upload_task(session, root, free)
    assert await queue.start(mine.id) is StartOutcome.STARTED


async def test_stale_in_progress_is_failed_when_a_job_starts(
    session: AsyncSession, root: Path
) -> None:
    assert STALE_AFTER == timedelta(minutes=15)
    user = await make_user(session)
    stuck = [await upload_task(session, root, user) for _ in range(3)]
    for task in stuck:
        await set_state(session, task, "in_progress", NOW - STALE_AFTER - timedelta(seconds=1))
    waiting = await upload_task(session, root, user)
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    assert await queue.start(waiting.id) is StartOutcome.STARTED  # the stuck ones freed the slots
    for task in stuck:
        document = await document_of(session, task)
        assert document.generation_status == "failed"
        assert document.generation_error == STALE_MESSAGE
        assert document.generation_completed_at == NOW


async def test_in_progress_of_exactly_fifteen_minutes_is_not_stale(
    session: AsyncSession, root: Path
) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    await set_state(session, task, "in_progress", NOW - STALE_AFTER)
    document = await DocumentQueueService(session, clock=clock_at(NOW)).get(task.id)
    assert document.generation_status == "in_progress"


async def test_get_fails_a_stale_document_and_says_why(session: AsyncSession, root: Path) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    await set_state(session, task, "in_progress", NOW - timedelta(minutes=16))
    document = await DocumentQueueService(session, clock=clock_at(NOW)).get(task.id)
    assert document.generation_status == "failed"
    assert document.generation_error == STALE_MESSAGE
    assert "다시 업로드" in STALE_MESSAGE


async def test_get_of_a_task_without_document_is_document_not_found(
    session: AsyncSession,
) -> None:
    with pytest.raises(DocumentNotFoundError) as caught:
        await DocumentQueueService(session).get(uuid.uuid4())
    assert caught.value.code == "document_not_found"
    assert caught.value.message == "이 Task에는 아직 학습 문서가 없습니다."


async def test_complete_stores_the_content_and_never_overwrites(
    session: AsyncSession, root: Path
) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    await DocumentQueueService(session, clock=clock_at(NOW)).start(task.id)
    later = DocumentQueueService(session, clock=clock_at(NOW + timedelta(seconds=20)))
    assert await later.complete(task.id, valid_doc()) is True
    document = await document_of(session, task)
    assert document.generation_status == "completed"
    assert document.content == valid_doc()
    assert document.generation_completed_at == NOW + timedelta(seconds=20)
    assert document.generation_error is None
    # a repeated run must not touch a completed document
    assert await later.complete(task.id, empty_content()) is False
    assert await later.fail(task.id, "x") is False
    document = await document_of(session, task)
    assert document.generation_status == "completed"
    assert document.content == valid_doc()


async def test_complete_needs_in_progress(session: AsyncSession, root: Path) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    assert await queue.complete(task.id, valid_doc()) is False  # still pending
    await set_state(session, task, "failed", NOW)
    assert await queue.complete(task.id, valid_doc()) is False  # already failed (stale)
    assert (await document_of(session, task)).content == empty_content()


async def test_fail_records_the_learner_message(session: AsyncSession, root: Path) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    await queue.start(task.id)
    assert await queue.fail(task.id, "학습자 문구") is True
    document = await document_of(session, task)
    assert document.generation_status == "failed"
    assert document.generation_error == "학습자 문구"
    assert document.generation_completed_at == NOW
    assert document.content == empty_content()


async def test_fail_unsent_leaves_a_running_document_alone(
    session: AsyncSession, root: Path
) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    await queue.start(task.id)
    assert await queue.fail_unsent(task.id, "x") is False
    assert (await document_of(session, task)).generation_status == "in_progress"
    other = await upload_task(session, root, user)
    assert await queue.fail_unsent(other.id, "접수 실패") is True
    assert (await document_of(session, other)).generation_status == "failed"


async def test_describe_pending(session: AsyncSession, root: Path) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    status = queue.describe(task, await queue.get(task.id), "안내")
    assert status.status == "pending"
    assert status.elapsed_seconds is None
    assert status.estimated_total_seconds == 20
    assert status.notice == "안내"
    assert status.error is None
    assert status.generation_started_at is None


async def test_describe_in_progress_computes_elapsed_on_the_server(
    session: AsyncSession, root: Path
) -> None:
    user = await make_user(session)
    created = await upload_task(session, root, user, code="x = 1\n" * 100)
    task = await TaskService(session).get(user.id, created.id)
    await set_state(session, task, "in_progress", NOW - timedelta(seconds=12, milliseconds=900))
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    status = queue.describe(task, await queue.get(task.id), None)
    assert status.status == "in_progress"
    assert status.elapsed_seconds == 12
    assert status.estimated_total_seconds == 40  # 15 + 0.25 * 100
    assert status.notice is None


async def test_describe_finished_documents_hide_estimate_elapsed_and_notice(
    session: AsyncSession, root: Path
) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    await queue.start(task.id)
    await queue.fail(task.id, "문서를 만들지 못했습니다.")
    status = queue.describe(task, await queue.get(task.id), "낡은 안내")
    assert status.status == "failed"
    assert status.error == "문서를 만들지 못했습니다."
    assert status.estimated_total_seconds is None
    assert status.elapsed_seconds is None
    assert status.notice is None
    assert status.generation_completed_at == NOW


async def test_describe_completed_has_no_error(session: AsyncSession, root: Path) -> None:
    user = await make_user(session)
    task = await upload_task(session, root, user)
    queue = DocumentQueueService(session, clock=clock_at(NOW))
    await queue.start(task.id)
    await queue.complete(task.id, valid_doc())
    status = queue.describe(task, await queue.get(task.id), None)
    assert (status.status, status.error, status.estimated_total_seconds) == (
        "completed",
        None,
        None,
    )
