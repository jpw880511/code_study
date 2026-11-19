import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Engine, Table, func, inspect, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.models import Project, Task, UploadedCode, User

MAX_UPLOAD_BYTES = 10485760


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


def new_upload(task: Task, **values: object) -> UploadedCode:
    return UploadedCode(task_id=task.id, **values)


async def count_uploads(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(UploadedCode))).scalar_one()


async def test_database_fills_in_the_defaults(session: AsyncSession) -> None:
    upload = new_upload(await saved_task(session))
    session.add(upload)
    await session.flush()

    # No refresh(): the values must already be loaded (async sessions cannot lazy-load).
    assert upload.id is not None
    for value in (
        upload.detected_language,
        upload.complexity_level,
        upload.total_lines,
        upload.total_files,
        upload.upload_size_bytes,
    ):
        assert value is None
    assert upload.created_at.tzinfo is not None
    assert abs(upload.created_at - datetime.now(UTC)) < timedelta(minutes=1)


async def test_analysis_results_round_trip(session: AsyncSession) -> None:
    session.add(
        new_upload(
            await saved_task(session),
            detected_language="python",
            complexity_level="intermediate",
            total_lines=120,
            total_files=3,
            upload_size_bytes=4096,
        )
    )
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(UploadedCode))).scalar_one()
    assert stored.detected_language == "python"
    assert stored.complexity_level == "intermediate"
    assert (stored.total_lines, stored.total_files, stored.upload_size_bytes) == (120, 3, 4096)


@pytest.mark.parametrize("level", ["beginner", "intermediate", "advanced"])
async def test_complexity_level_accepts_the_three_known_values(
    session: AsyncSession, level: str
) -> None:
    upload = new_upload(await saved_task(session), complexity_level=level)
    session.add(upload)
    await session.flush()
    assert upload.complexity_level == level


async def test_complexity_level_rejects_anything_else(session: AsyncSession) -> None:
    session.add(new_upload(await saved_task(session), complexity_level="expert"))
    with pytest.raises(IntegrityError, match="uploaded_code_complexity_level_check"):
        await session.flush()


async def test_upload_size_is_limited_to_10_megabytes(session: AsyncSession) -> None:
    session.add(new_upload(await saved_task(session, 1), upload_size_bytes=MAX_UPLOAD_BYTES))
    await session.flush()
    session.add(new_upload(await saved_task(session, 2), upload_size_bytes=MAX_UPLOAD_BYTES + 1))
    with pytest.raises(IntegrityError, match="valid_upload_size"):
        await session.flush()


async def test_task_id_is_required(session: AsyncSession) -> None:
    session.add(UploadedCode())
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_upload_must_belong_to_an_existing_task(session: AsyncSession) -> None:
    session.add(UploadedCode(task_id=uuid.uuid4()))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_a_task_cannot_have_two_uploads(session: AsyncSession) -> None:
    task = await saved_task(session)
    session.add(new_upload(task))
    await session.flush()

    session.add(new_upload(task))
    with pytest.raises(IntegrityError, match="uploaded_code_task_id_key"):
        await session.flush()


async def test_task_loads_its_upload_and_the_upload_loads_its_task(session: AsyncSession) -> None:
    task = await saved_task(session)
    session.add(new_upload(task, detected_language="go"))
    await session.flush()
    session.expunge_all()

    loaded_task = (
        await session.execute(select(Task).options(selectinload(Task.uploaded_code)))
    ).scalar_one()
    assert loaded_task.uploaded_code is not None
    assert loaded_task.uploaded_code.detected_language == "go"

    session.expunge_all()
    upload = (
        await session.execute(select(UploadedCode).options(selectinload(UploadedCode.task)))
    ).scalar_one()
    assert upload.task.title == "첫 번째 작업"


async def test_a_task_without_an_upload_loads_none(session: AsyncSession) -> None:
    await saved_task(session)
    session.expunge_all()

    task = (
        await session.execute(select(Task).options(selectinload(Task.uploaded_code)))
    ).scalar_one()

    assert task.uploaded_code is None


async def test_relationships_must_be_loaded_explicitly_in_async_code(session: AsyncSession) -> None:
    session.add(new_upload(await saved_task(session)))
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(Task))).scalar_one()

    with pytest.raises(InvalidRequestError):
        _ = stored.uploaded_code


async def test_deleting_a_task_deletes_its_upload(session: AsyncSession) -> None:
    task = await saved_task(session)
    session.add(new_upload(task))
    await session.flush()
    session.expunge_all()
    loaded = (
        await session.execute(select(Task).options(selectinload(Task.uploaded_code)))
    ).scalar_one()

    await session.delete(loaded)
    await session.flush()

    assert await count_uploads(session) == 0


async def test_deleting_a_project_deletes_the_uploads_of_its_tasks(session: AsyncSession) -> None:
    task = await saved_task(session)
    session.add(new_upload(task))
    await session.flush()
    project = (await session.execute(select(Project))).scalar_one()

    await session.delete(project)
    await session.flush()

    assert await count_uploads(session) == 0


def test_model_matches_the_migrated_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table = cast(Table, UploadedCode.__table__)

    db_columns = {c["name"]: c for c in inspector.get_columns("uploaded_code")}
    assert set(db_columns) == set(table.c.keys())
    for model_column in table.c:
        db_column = db_columns[model_column.name]
        assert db_column["nullable"] == model_column.nullable, model_column.name
        db_length = getattr(db_column["type"], "length", None)
        assert db_length == getattr(model_column.type, "length", None), model_column.name

    assert str(db_columns["id"]["default"]).startswith("gen_random_uuid()")
    assert "CURRENT_TIMESTAMP" in str(db_columns["created_at"]["default"])
    for name in (
        "task_id",
        "detected_language",
        "complexity_level",
        "total_lines",
        "total_files",
        "upload_size_bytes",
    ):
        assert db_columns[name]["default"] is None, name

    assert inspector.get_pk_constraint("uploaded_code")["constrained_columns"] == ["id"]

    (foreign_key,) = inspector.get_foreign_keys("uploaded_code")
    assert foreign_key["constrained_columns"] == ["task_id"]
    assert foreign_key["referred_table"] == "tasks"
    assert foreign_key["options"]["ondelete"] == "CASCADE"

    db_indexes = {i["name"]: i for i in inspector.get_indexes("uploaded_code")}
    for index in table.indexes:
        assert db_indexes[index.name]["column_names"] == [c.name for c in index.columns]
    # The unique constraint is reported as an index too; it is not one of the model's indexes.
    assert set(db_indexes) - {i.name for i in table.indexes} <= {"uploaded_code_task_id_key"}

    uniques = inspector.get_unique_constraints("uploaded_code")
    assert [(u["name"], u["column_names"]) for u in uniques] == [
        ("uploaded_code_task_id_key", ["task_id"])
    ]

    db_checks = {c["name"] for c in inspector.get_check_constraints("uploaded_code")}
    model_checks = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert model_checks == db_checks
