"""The worker's job, run as an ordinary function against a database that really commits.

The AI is a fake and Redis is a dictionary: nothing here reaches the network.
"""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.models import LearningDocument, Task, User
from src.models.learning_document import empty_content
from src.services.ai.errors import AIServiceUnavailableError
from src.services.ai.gemini_client import GeminiResponse
from src.services.code_analysis.file_storage import FileStorage
from src.services.document.document_notice_store import NoticeStore
from src.services.document.document_queue_service import (
    TIMEOUT_MESSAGE,
    UNKNOWN_ERROR_MESSAGE,
    DocumentQueueService,
)
from src.services.document.errors import DocumentGenerationError
from src.services.task_errors import TaskNotFoundError
from src.services.task_service import TaskService
from src.tasks.document_generation import (
    COMPLETED,
    DEFERRED,
    FAILED,
    SKIPPED,
    generate_for_task,
)
from tests.document_fixtures import valid_doc
from tests.queue_helpers import MemoryRedis, make_user, upload_task

SECRET = "api_key = 'hunter2-secret-in-the-code'"


def answer(doc: Any) -> GeminiResponse:
    return GeminiResponse(
        text=json.dumps(doc, ensure_ascii=False), model="fake", prompt_tokens=10,
        completion_tokens=20, thinking_tokens=5, finish_reason="STOP",
    )  # fmt: skip


class FakeClient:
    """Plays back one outcome per call (an answer or an exception); then valid answers."""

    def __init__(self, *outcomes: Any, delay: float = 0) -> None:
        self.outcomes = list(outcomes)
        self.prompts: list[str] = []
        self.delay = delay

    async def generate(self, prompt: str, **options: Any) -> GeminiResponse:
        self.prompts.append(prompt)
        await asyncio.sleep(self.delay)
        outcome = self.outcomes.pop(0) if self.outcomes else answer(valid_doc())
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, GeminiResponse)
        return outcome


async def no_sleep(_: float) -> None:
    return None


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def redis_fake() -> MemoryRedis:
    return MemoryRedis()


async def seed(
    factory: async_sessionmaker[AsyncSession], root: Path, count: int = 1, code: str | None = None
) -> tuple[User, list[Task]]:
    async with factory() as db:
        user = await make_user(db)
        extra: dict[str, Any] = {} if code is None else {"code": code}
        tasks = [await upload_task(db, root, user, **extra) for _ in range(count)]
        await db.commit()
    return user, tasks


async def run(
    factory: async_sessionmaker[AsyncSession],
    root: Path,
    task: Task,
    client: FakeClient,
    notices: NoticeStore,
) -> str:
    return await generate_for_task(
        task.id,
        session_factory=factory,
        storage=FileStorage(root),
        client=client,  # type: ignore[arg-type]
        notices=notices,
        sleep=no_sleep,
    )


async def document_of(factory: async_sessionmaker[AsyncSession], task: Task) -> LearningDocument:
    async with factory() as db:
        return (
            await db.execute(select(LearningDocument).where(LearningDocument.task_id == task.id))
        ).scalar_one()


async def test_a_pending_document_is_generated_and_stored(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    client = FakeClient()
    notices = NoticeStore(redis_fake)
    await notices.set(task.id, "낡은 안내")
    assert await run(committed_factory, root, task, client, notices) == COMPLETED
    document = await document_of(committed_factory, task)
    assert document.generation_status == "completed"
    assert document.content["chapter1"]["summary"] == valid_doc()["chapter1"]["summary"]
    assert document.generation_started_at is not None
    assert document.generation_completed_at is not None
    assert document.generation_error is None
    assert len(client.prompts) == 1
    assert "line1 = 1" in client.prompts[0]  # the stored code went into the prompt
    assert await notices.get(task.id) is None  # cleared when done


async def test_the_same_job_run_twice_generates_once(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    client = FakeClient()
    notices = NoticeStore(redis_fake)
    assert await run(committed_factory, root, task, client, notices) == COMPLETED
    first = await document_of(committed_factory, task)
    assert await run(committed_factory, root, task, client, notices) == SKIPPED
    second = await document_of(committed_factory, task)
    assert len(client.prompts) == 1
    assert second.content == first.content
    assert second.generation_completed_at == first.generation_completed_at


async def test_two_workers_at_once_generate_once(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    client = FakeClient(delay=0.05)
    notices = NoticeStore(redis_fake)
    outcomes = await asyncio.gather(
        *(run(committed_factory, root, task, client, notices) for _ in range(4))
    )
    assert sorted(outcomes) == [COMPLETED, SKIPPED, SKIPPED, SKIPPED]
    assert len(client.prompts) == 1


async def test_a_completed_document_is_not_made_again(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    async with committed_factory() as db:
        await db.execute(
            update(LearningDocument)
            .where(LearningDocument.task_id == task.id)
            .values(generation_status="completed", content=valid_doc())
        )
        await db.commit()
    client = FakeClient()
    assert await run(committed_factory, root, task, client, NoticeStore(redis_fake)) == SKIPPED
    assert client.prompts == []


async def test_a_task_without_document_is_skipped(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    async with committed_factory() as db:
        await db.execute(
            update(LearningDocument)
            .where(LearningDocument.task_id == task.id)
            .values(generation_status="failed")
        )
        await db.commit()
    client = FakeClient()
    assert await run(committed_factory, root, task, client, NoticeStore(redis_fake)) == SKIPPED


async def test_the_fourth_document_of_a_user_waits_in_pending(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, tasks = await seed(committed_factory, root, count=4)
    async with committed_factory() as db:
        for task in tasks[:3]:
            await DocumentQueueService(db).start(task.id)
        await db.commit()
    client = FakeClient()
    outcome = await run(committed_factory, root, tasks[3], client, NoticeStore(redis_fake))
    assert outcome == DEFERRED
    assert client.prompts == []
    assert (await document_of(committed_factory, tasks[3])).generation_status == "pending"


async def test_many_workers_at_once_never_exceed_three_per_user(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, tasks = await seed(committed_factory, root, count=6)
    client = FakeClient(delay=0.1)
    notices = NoticeStore(redis_fake)
    outcomes = await asyncio.gather(
        *(run(committed_factory, root, task, client, notices) for task in tasks)
    )
    assert sorted(outcomes) == [COMPLETED] * 3 + [DEFERRED] * 3
    assert len(client.prompts) == 3


async def test_retry_notices_go_to_redis_while_waiting(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    seen: list[str | None] = []
    notices = NoticeStore(redis_fake)

    class Watching(FakeClient):
        async def generate(self, prompt: str, **options: Any) -> GeminiResponse:
            seen.append(await notices.get(task.id))
            return await super().generate(prompt, **options)

    client = Watching(AIServiceUnavailableError(status_code=503))
    assert await run(committed_factory, root, task, client, notices) == COMPLETED
    assert seen == [None, "AI 서비스가 바빠 다시 시도하는 중입니다 (1/3)."]
    assert await notices.get(task.id) is None


async def test_a_service_failure_is_stored_in_the_words_of_the_service(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    notices = NoticeStore(redis_fake)
    await notices.set(task.id, "안내")
    busy = AIServiceUnavailableError(status_code=503)
    client = FakeClient(busy, busy, busy, busy)
    assert await run(committed_factory, root, task, client, notices) == FAILED
    document = await document_of(committed_factory, task)
    assert document.generation_status == "failed"
    assert document.generation_error == AIServiceUnavailableError.default_message
    assert document.generation_completed_at is not None
    assert document.content == empty_content()
    assert await notices.get(task.id) is None


async def test_an_unusable_answer_is_stored_with_the_generation_message(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    client = FakeClient(*[answer({"chapter1": {}}) for _ in range(3)])
    assert await run(committed_factory, root, task, client, NoticeStore(redis_fake)) == FAILED
    document = await document_of(committed_factory, task)
    assert document.generation_error == DocumentGenerationError.default_message


async def test_an_unexpected_error_leaves_only_the_general_message_and_no_code_in_logs(
    committed_factory: async_sessionmaker[AsyncSession],
    root: Path,
    redis_fake: MemoryRedis,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, (task,) = await seed(committed_factory, root, code=f"{SECRET}\nx = 1\n")
    client = FakeClient(RuntimeError(f"boom while reading {SECRET}"))
    caplog.set_level(logging.DEBUG)
    assert await run(committed_factory, root, task, client, NoticeStore(redis_fake)) == FAILED
    document = await document_of(committed_factory, task)
    assert document.generation_error == UNKNOWN_ERROR_MESSAGE
    assert UNKNOWN_ERROR_MESSAGE == (
        "문서를 만드는 중 알 수 없는 오류가 발생했습니다. "
        "잠시 후 다시 시도하거나 고객지원에 문의하세요."
    )
    assert "hunter2" not in caplog.text
    assert "RuntimeError" in caplog.text  # the kind of the error is logged, nothing else of it
    assert str(task.id) in caplog.text
    assert "hunter2" not in (document.generation_error or "")
    assert document.content == empty_content()


async def test_the_failure_of_the_ai_logs_its_kind_and_status_but_no_prompt(
    committed_factory: async_sessionmaker[AsyncSession],
    root: Path,
    redis_fake: MemoryRedis,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, (task,) = await seed(committed_factory, root, code=f"{SECRET}\nx = 1\n")
    client = FakeClient(AIServiceUnavailableError(status_code=503))
    client.outcomes += [AIServiceUnavailableError(status_code=503)] * 3
    caplog.set_level(logging.DEBUG)
    assert await run(committed_factory, root, task, client, NoticeStore(redis_fake)) == FAILED
    assert "AIServiceUnavailableError" in caplog.text
    assert "503" in caplog.text
    assert "hunter2" not in caplog.text


async def test_the_soft_time_limit_is_a_failure_with_its_own_message(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    client = FakeClient(SoftTimeLimitExceeded())
    assert await run(committed_factory, root, task, client, NoticeStore(redis_fake)) == FAILED
    assert (await document_of(committed_factory, task)).generation_error == TIMEOUT_MESSAGE


async def test_a_trashed_task_fails_the_document_with_the_task_message(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    user, (task,) = await seed(committed_factory, root)
    async with committed_factory() as db:
        await TaskService(db).soft_delete(user.id, task.id)
        await db.commit()
    client = FakeClient()
    assert await run(committed_factory, root, task, client, NoticeStore(redis_fake)) == FAILED
    document = await document_of(committed_factory, task)
    assert (
        document.generation_error
        == "요청한 Task를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 Task입니다."
    )
    assert client.prompts == []


async def test_a_missing_code_file_fails_the_document(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)
    shutil.rmtree(root)
    client = FakeClient()
    assert await run(committed_factory, root, task, client, NoticeStore(redis_fake)) == FAILED
    document = await document_of(committed_factory, task)
    assert document.generation_error == "저장된 코드 파일을 찾을 수 없습니다."
    assert client.prompts == []


async def test_a_document_already_failed_as_stale_is_not_overwritten_by_a_late_result(
    committed_factory: async_sessionmaker[AsyncSession], root: Path, redis_fake: MemoryRedis
) -> None:
    _, (task,) = await seed(committed_factory, root)

    class Slow(FakeClient):
        async def generate(self, prompt: str, **options: Any) -> GeminiResponse:
            async with committed_factory() as db:  # meanwhile the page's status call gave up
                await DocumentQueueService(db).fail(task.id, "시간 초과")
                await db.commit()
            return await super().generate(prompt, **options)

    assert await run(committed_factory, root, task, Slow(), NoticeStore(redis_fake)) == SKIPPED
    document = await document_of(committed_factory, task)
    assert document.generation_status == "failed"
    assert document.generation_error == "시간 초과"
    assert document.content == empty_content()


async def test_a_task_that_vanishes_after_the_claim_fails_the_document(
    committed_factory: async_sessionmaker[AsyncSession],
    root: Path,
    redis_fake: MemoryRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, (task,) = await seed(committed_factory, root)
    real_owner_id = DocumentQueueService.owner_id
    calls = 0

    async def owner_gone_after_the_claim(self: DocumentQueueService, task_id: Any) -> Any:
        nonlocal calls
        calls += 1
        return await real_owner_id(self, task_id) if calls == 1 else None

    monkeypatch.setattr(DocumentQueueService, "owner_id", owner_gone_after_the_claim)
    client = FakeClient()
    assert await run(committed_factory, root, task, client, NoticeStore(redis_fake)) == FAILED
    document = await document_of(committed_factory, task)
    assert document.generation_error == TaskNotFoundError.default_message
    assert client.prompts == []
