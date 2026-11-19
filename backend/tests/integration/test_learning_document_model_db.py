import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Engine, Table, func, inspect, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DBAPIError, IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.models import LearningDocument, Project, Task, User
from src.models.learning_document import CHAPTER_KEYS, GENERATION_STATUSES, empty_content

FULL_CONTENT = {
    "chapter1": {"title": "이 코드가 하는 일", "summary": "두 수를 더합니다."},
    "chapter2": {"title": "미리 알아야 할 것", "concepts": [{"name": "변수", "analogy": "상자"}]},
    "chapter3": {"title": "코드 구조", "flowchart": "A -> B"},
    "chapter4": {"title": "한 줄씩 설명", "explanations": [{"line": 1, "text": "함수를 만듭니다"}]},
    "chapter5": {"title": "실행 흐름", "steps": [1, 2, 3]},
    "chapter6": {"title": "핵심 개념", "concepts": []},
    "chapter7": {"title": "흔한 실수", "mistakes": [{"wrong": "a", "right": "b"}]},
}


async def saved_task(session: AsyncSession, number: int = 1) -> Task:
    user = User(email=f"{uuid.uuid4().hex}@example.com", password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, title="프로젝트")
    session.add(project)
    await session.flush()
    task = Task(project_id=project.id, task_number=number, title="첫 번째 작업")
    session.add(task)
    await session.flush()
    return task


def new_document(task: Task, **values: object) -> LearningDocument:
    return LearningDocument(task_id=task.id, **values)


async def count_documents(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(LearningDocument))).scalar_one()


async def test_a_new_document_is_pending_with_seven_empty_chapters(session: AsyncSession) -> None:
    document = new_document(await saved_task(session))
    session.add(document)
    await session.flush()

    # No refresh(): the values must already be loaded (async sessions cannot lazy-load).
    assert document.id is not None
    assert document.generation_status == "pending"
    assert document.content == empty_content()
    for value in (
        document.generation_started_at,
        document.generation_completed_at,
        document.generation_error,
        document.celery_task_id,
    ):
        assert value is None
    for stamp in (document.created_at, document.updated_at):
        assert stamp.tzinfo is not None
        assert abs(stamp - datetime.now(UTC)) < timedelta(minutes=1)


async def test_the_generated_content_round_trips_with_korean_and_nesting(
    session: AsyncSession,
) -> None:
    session.add(new_document(await saved_task(session), content=FULL_CONTENT))
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(LearningDocument))).scalar_one()

    assert stored.content == FULL_CONTENT


async def test_replacing_the_content_is_saved(session: AsyncSession) -> None:
    document = new_document(await saved_task(session))
    session.add(document)
    await session.flush()

    document.content = FULL_CONTENT
    await session.flush()
    session.expunge_all()

    assert (await session.execute(select(LearningDocument))).scalar_one().content == FULL_CONTENT


async def test_the_whole_lifecycle_is_stored(session: AsyncSession) -> None:
    document = new_document(await saved_task(session))
    session.add(document)
    await session.flush()
    started = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
    finished = started + timedelta(minutes=2)

    document.generation_status = "completed"
    document.generation_started_at = started
    document.generation_completed_at = finished
    document.celery_task_id = "7c1e5d0e-0000-4000-8000-000000000000"
    document.content = FULL_CONTENT
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(LearningDocument))).scalar_one()
    assert stored.generation_status == "completed"
    assert stored.generation_started_at == started
    assert stored.generation_completed_at == finished
    assert stored.celery_task_id == "7c1e5d0e-0000-4000-8000-000000000000"


async def test_a_failure_keeps_its_error_message(session: AsyncSession) -> None:
    message = "AI 서비스가 응답하지 않습니다. " * 100
    document = new_document(await saved_task(session), generation_status="failed")
    document.generation_error = message
    session.add(document)
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(LearningDocument))).scalar_one()
    assert stored.generation_error == message


async def test_updating_a_document_refreshes_updated_at_without_a_reload(
    session: AsyncSession,
) -> None:
    document = new_document(await saved_task(session))
    session.add(document)
    await session.flush()
    old = datetime(2020, 1, 1, tzinfo=UTC)
    document.updated_at = old
    await session.flush()

    document.generation_status = "in_progress"
    await session.flush()

    assert document.updated_at > old


@pytest.mark.parametrize("status", GENERATION_STATUSES)
async def test_every_known_status_is_accepted(session: AsyncSession, status: str) -> None:
    document = new_document(await saved_task(session), generation_status=status)
    session.add(document)
    await session.flush()
    assert document.generation_status == status


@pytest.mark.parametrize("status", ["done", "PENDING", "", "queued"])
async def test_any_other_status_is_rejected(session: AsyncSession, status: str) -> None:
    session.add(new_document(await saved_task(session), generation_status=status))
    with pytest.raises(IntegrityError, match="learning_documents_generation_status_check"):
        await session.flush()


async def test_every_chapter_is_required_in_the_content(session: AsyncSession) -> None:
    task = await saved_task(session)
    for missing in CHAPTER_KEYS:
        content = {key: {} for key in CHAPTER_KEYS if key != missing}
        session.add(new_document(task, content=content))
        with pytest.raises(IntegrityError, match="valid_content_structure"):
            await session.flush()
        await session.rollback()
        task = await saved_task(session)


@pytest.mark.parametrize("content", [[], "chapter1", 7, None])
async def test_the_content_must_be_an_object(session: AsyncSession, content: object) -> None:
    session.add(new_document(await saved_task(session), content=content))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_extra_keys_and_empty_chapters_are_allowed(session: AsyncSession) -> None:
    content = {key: None for key in CHAPTER_KEYS} | {"notes": "extra"}
    document = new_document(await saved_task(session), content=content)
    session.add(document)
    await session.flush()
    assert document.content == content


async def test_task_id_is_required(session: AsyncSession) -> None:
    session.add(LearningDocument())
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_a_document_must_belong_to_an_existing_task(session: AsyncSession) -> None:
    session.add(LearningDocument(task_id=uuid.uuid4()))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_a_task_cannot_have_two_documents(session: AsyncSession) -> None:
    task = await saved_task(session)
    session.add(new_document(task))
    await session.flush()

    session.add(new_document(task))
    with pytest.raises(IntegrityError, match="learning_documents_task_id_key"):
        await session.flush()


async def test_the_celery_task_id_is_limited_to_255_characters(session: AsyncSession) -> None:
    session.add(new_document(await saved_task(session, 1), celery_task_id="c" * 255))
    await session.flush()
    session.add(new_document(await saved_task(session, 2), celery_task_id="c" * 256))
    with pytest.raises(DBAPIError):
        await session.flush()


async def test_task_loads_its_document_and_the_document_loads_its_task(
    session: AsyncSession,
) -> None:
    task = await saved_task(session)
    session.add(new_document(task, content=FULL_CONTENT))
    await session.flush()
    session.expunge_all()

    loaded_task = (
        await session.execute(select(Task).options(selectinload(Task.learning_document)))
    ).scalar_one()
    assert loaded_task.learning_document is not None
    assert loaded_task.learning_document.content == FULL_CONTENT

    session.expunge_all()
    document = (
        await session.execute(select(LearningDocument).options(selectinload(LearningDocument.task)))
    ).scalar_one()
    assert document.task.title == "첫 번째 작업"


async def test_a_task_without_a_document_loads_none(session: AsyncSession) -> None:
    await saved_task(session)
    session.expunge_all()

    task = (
        await session.execute(select(Task).options(selectinload(Task.learning_document)))
    ).scalar_one()

    assert task.learning_document is None


async def test_relationships_must_be_loaded_explicitly_in_async_code(session: AsyncSession) -> None:
    session.add(new_document(await saved_task(session)))
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(Task))).scalar_one()

    with pytest.raises(InvalidRequestError):
        _ = stored.learning_document


async def test_deleting_a_task_deletes_its_document(session: AsyncSession) -> None:
    session.add(new_document(await saved_task(session)))
    await session.flush()
    session.expunge_all()
    loaded = (
        await session.execute(select(Task).options(selectinload(Task.learning_document)))
    ).scalar_one()

    await session.delete(loaded)
    await session.flush()

    assert await count_documents(session) == 0


async def test_deleting_a_project_deletes_the_documents_of_its_tasks(session: AsyncSession) -> None:
    session.add(new_document(await saved_task(session)))
    await session.flush()
    project = (await session.execute(select(Project))).scalar_one()

    await session.delete(project)
    await session.flush()

    assert await count_documents(session) == 0


def test_model_matches_the_migrated_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table = cast(Table, LearningDocument.__table__)

    db_columns = {c["name"]: c for c in inspector.get_columns("learning_documents")}
    assert set(db_columns) == set(table.c.keys())
    for model_column in table.c:
        db_column = db_columns[model_column.name]
        assert db_column["nullable"] == model_column.nullable, model_column.name
        db_length = getattr(db_column["type"], "length", None)
        assert db_length == getattr(model_column.type, "length", None), model_column.name
    assert isinstance(db_columns["content"]["type"], JSONB)

    assert str(db_columns["id"]["default"]).startswith("gen_random_uuid()")
    for name in ("created_at", "updated_at"):
        assert "CURRENT_TIMESTAMP" in str(db_columns[name]["default"]), name
    assert "'pending'" in str(db_columns["generation_status"]["default"])
    for name in (
        "task_id",
        "content",
        "generation_started_at",
        "generation_completed_at",
        "generation_error",
        "celery_task_id",
    ):
        assert db_columns[name]["default"] is None, name

    assert inspector.get_pk_constraint("learning_documents")["constrained_columns"] == ["id"]

    (foreign_key,) = inspector.get_foreign_keys("learning_documents")
    assert foreign_key["constrained_columns"] == ["task_id"]
    assert foreign_key["referred_table"] == "tasks"
    assert foreign_key["options"]["ondelete"] == "CASCADE"

    db_indexes = {i["name"]: i for i in inspector.get_indexes("learning_documents")}
    for index in table.indexes:
        assert db_indexes[index.name]["column_names"] == [c.name for c in index.columns]
    # The unique constraint is reported as an index too; it is not one of the model's indexes.
    extra = set(db_indexes) - {i.name for i in table.indexes}
    assert extra <= {"learning_documents_task_id_key"}

    uniques = inspector.get_unique_constraints("learning_documents")
    assert [(u["name"], u["column_names"]) for u in uniques] == [
        ("learning_documents_task_id_key", ["task_id"])
    ]

    db_checks = {
        c["name"]: c["sqltext"] for c in inspector.get_check_constraints("learning_documents")
    }
    model_checks = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert model_checks == set(db_checks)
    for key in CHAPTER_KEYS:
        assert f"'{key}'" in db_checks["valid_content_structure"]
