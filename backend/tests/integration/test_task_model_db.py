import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Engine, Table, func, inspect, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.models import Project, Task, User


async def saved_project(session: AsyncSession, email: str = "student@example.com") -> Project:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, title="프로젝트")
    session.add(project)
    await session.flush()
    return project


def new_task(
    project: Project, number: int = 1, title: str = "첫 번째 작업", **values: object
) -> Task:
    return Task(project_id=project.id, task_number=number, title=title, **values)


async def count_tasks(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Task))).scalar_one()


async def test_database_fills_in_the_defaults(session: AsyncSession) -> None:
    task = new_task(await saved_project(session))
    session.add(task)
    await session.flush()

    # No refresh(): the values must already be loaded (async sessions cannot lazy-load).
    assert task.id is not None
    assert task.description is None
    assert task.upload_method is None
    assert task.deletion_status == "active"
    assert task.trashed_at is None
    assert task.scheduled_deletion_at is None
    for value in (task.created_at, task.updated_at):
        assert value.tzinfo is not None
        assert abs(value - datetime.now(UTC)) < timedelta(minutes=1)


async def test_trash_fields_round_trip(session: AsyncSession) -> None:
    task = new_task(await saved_project(session))
    session.add(task)
    await session.flush()
    trashed_at = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)

    task.deletion_status = "trashed"
    task.trashed_at = trashed_at
    task.scheduled_deletion_at = trashed_at + timedelta(days=30)
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(Task))).scalar_one()
    assert stored.deletion_status == "trashed"
    assert stored.trashed_at == trashed_at
    assert stored.scheduled_deletion_at == trashed_at + timedelta(days=30)


async def test_updating_a_task_refreshes_updated_at_without_a_reload(session: AsyncSession) -> None:
    task = new_task(await saved_project(session))
    session.add(task)
    await session.flush()
    old = datetime(2020, 1, 1, tzinfo=UTC)
    task.updated_at = old
    await session.flush()

    task.title = "바뀐 작업 제목"
    await session.flush()

    assert task.updated_at > old


@pytest.mark.parametrize("method", ["file", "folder", "paste"])
async def test_upload_method_accepts_the_three_known_values(
    session: AsyncSession, method: str
) -> None:
    task = new_task(await saved_project(session), upload_method=method)
    session.add(task)
    await session.flush()
    assert task.upload_method == method


async def test_upload_method_rejects_anything_else(session: AsyncSession) -> None:
    session.add(new_task(await saved_project(session), upload_method="zip"))
    with pytest.raises(IntegrityError, match="tasks_upload_method_check"):
        await session.flush()


async def test_deletion_status_only_accepts_the_two_known_values(session: AsyncSession) -> None:
    session.add(new_task(await saved_project(session), deletion_status="purged"))
    with pytest.raises(IntegrityError, match="tasks_deletion_status_check"):
        await session.flush()


async def test_title_needs_at_least_five_characters(session: AsyncSession) -> None:
    project = await saved_project(session)
    session.add(new_task(project, 1, "가" * 5))
    await session.flush()
    session.add(new_task(project, 2, "가" * 4))
    with pytest.raises(IntegrityError, match="title_min_length"):
        await session.flush()


async def test_description_is_limited_to_500_characters(session: AsyncSession) -> None:
    project = await saved_project(session)
    session.add(new_task(project, 1, description="가" * 500))
    await session.flush()
    session.add(new_task(project, 2, description="가" * 501))
    with pytest.raises(IntegrityError, match="description_max_length"):
        await session.flush()


async def test_title_task_number_and_project_are_required(session: AsyncSession) -> None:
    project = await saved_project(session)
    for task in (
        Task(project_id=project.id, task_number=1),
        Task(project_id=project.id, title="번호 없는 작업"),
        Task(task_number=1, title="프로젝트 없는 작업"),
    ):
        session.add(task)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
        project = await saved_project(session, f"{uuid.uuid4().hex}@example.com")


async def test_task_number_is_unique_within_a_project_but_not_across_projects(
    session: AsyncSession,
) -> None:
    first = await saved_project(session)
    second = await saved_project(session, "other@example.com")
    session.add_all([new_task(first, 1), new_task(second, 1), new_task(first, 2)])
    await session.flush()

    session.add(new_task(first, 1, "중복 번호 작업"))
    with pytest.raises(IntegrityError, match="unique_task_number_per_project"):
        await session.flush()


async def test_task_must_belong_to_an_existing_project(session: AsyncSession) -> None:
    session.add(Task(project_id=uuid.uuid4(), task_number=1, title="유령 프로젝트 작업"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_project_loads_its_tasks_explicitly(session: AsyncSession) -> None:
    project = await saved_project(session)
    other = await saved_project(session, "other@example.com")
    session.add_all([new_task(project, 1, "작업 하나 A"), new_task(project, 2, "작업 둘 B")])
    session.add(new_task(other, 1, "남의 작업 C"))
    await session.flush()
    session.expunge_all()

    loaded = (
        await session.execute(
            select(Project).where(Project.id == project.id).options(selectinload(Project.tasks))
        )
    ).scalar_one()

    assert sorted(t.title for t in loaded.tasks) == ["작업 둘 B", "작업 하나 A"]


async def test_task_loads_its_project_explicitly(session: AsyncSession) -> None:
    session.add(new_task(await saved_project(session)))
    await session.flush()
    session.expunge_all()

    task = (await session.execute(select(Task).options(selectinload(Task.project)))).scalar_one()

    assert task.project.title == "프로젝트"


async def test_relationships_must_be_loaded_explicitly_in_async_code(session: AsyncSession) -> None:
    session.add(new_task(await saved_project(session)))
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(Project))).scalar_one()

    with pytest.raises(InvalidRequestError):
        _ = stored.tasks


async def test_deleting_a_project_deletes_its_tasks(session: AsyncSession) -> None:
    project = await saved_project(session)
    other = await saved_project(session, "other@example.com")
    session.add_all([new_task(project, 1, "지워질 작업 A"), new_task(other, 1, "남는 작업 B")])
    await session.flush()

    await session.delete(project)
    await session.flush()

    assert (await session.execute(select(Task.title))).scalars().all() == ["남는 작업 B"]


async def test_deleting_a_user_deletes_the_tasks_of_its_projects(session: AsyncSession) -> None:
    project = await saved_project(session)
    session.add(new_task(project))
    await session.flush()
    user = (await session.execute(select(User))).scalar_one()

    await session.delete(user)
    await session.flush()

    assert await count_tasks(session) == 0


def test_model_matches_the_migrated_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table = cast(Table, Task.__table__)

    db_columns = {c["name"]: c for c in inspector.get_columns("tasks")}
    assert set(db_columns) == set(table.c.keys())
    for model_column in table.c:
        db_column = db_columns[model_column.name]
        assert db_column["nullable"] == model_column.nullable, model_column.name
        db_length = getattr(db_column["type"], "length", None)
        assert db_length == getattr(model_column.type, "length", None), model_column.name

    assert str(db_columns["id"]["default"]).startswith("gen_random_uuid()")
    for name in ("created_at", "updated_at"):
        assert "CURRENT_TIMESTAMP" in str(db_columns[name]["default"]), name
    assert "'active'" in str(db_columns["deletion_status"]["default"])
    for name in ("task_number", "title", "description", "upload_method", "project_id"):
        assert db_columns[name]["default"] is None, name

    assert inspector.get_pk_constraint("tasks")["constrained_columns"] == ["id"]

    (foreign_key,) = inspector.get_foreign_keys("tasks")
    assert foreign_key["constrained_columns"] == ["project_id"]
    assert foreign_key["referred_table"] == "projects"
    assert foreign_key["options"]["ondelete"] == "CASCADE"

    db_indexes = {i["name"]: i for i in inspector.get_indexes("tasks")}
    for index in table.indexes:
        assert db_indexes[index.name]["column_names"] == [c.name for c in index.columns]
    # The unique constraint is reported as an index too; it is not one of the model's indexes.
    assert set(db_indexes) - {i.name for i in table.indexes} <= {"unique_task_number_per_project"}
    assert (
        "deletion_status"
        in db_indexes["idx_tasks_project_active"]["dialect_options"]["postgresql_where"]
    )

    uniques = inspector.get_unique_constraints("tasks")
    assert [(u["name"], u["column_names"]) for u in uniques] == [
        ("unique_task_number_per_project", ["project_id", "task_number"])
    ]

    db_checks = {c["name"]: c["sqltext"] for c in inspector.get_check_constraints("tasks")}
    model_checks = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert model_checks == set(db_checks)
