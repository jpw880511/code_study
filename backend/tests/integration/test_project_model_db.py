import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Engine, Table, func, inspect, select
from sqlalchemy.exc import DBAPIError, IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.models import Project, User


async def saved_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


def new_project(user: User, title: str = "첫 프로젝트", **values: object) -> Project:
    return Project(user_id=user.id, title=title, **values)


async def count_projects(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Project))).scalar_one()


async def test_database_fills_in_the_defaults(session: AsyncSession) -> None:
    project = new_project(await saved_user(session))
    session.add(project)
    await session.flush()

    # No refresh(): the values must already be loaded (async sessions cannot lazy-load).
    assert project.id is not None
    assert project.description is None
    assert project.deletion_status == "active"
    assert project.trashed_at is None
    assert project.scheduled_deletion_at is None
    for value in (project.created_at, project.updated_at, project.last_activity_at):
        assert value is not None
        assert value.tzinfo is not None
        assert abs(value - datetime.now(UTC)) < timedelta(minutes=1)


async def test_trash_fields_round_trip(session: AsyncSession) -> None:
    project = new_project(await saved_user(session))
    session.add(project)
    await session.flush()
    trashed_at = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)

    project.deletion_status = "trashed"
    project.trashed_at = trashed_at
    project.scheduled_deletion_at = trashed_at + timedelta(days=30)
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(Project))).scalar_one()
    assert stored.deletion_status == "trashed"
    assert stored.trashed_at == trashed_at
    assert stored.scheduled_deletion_at == trashed_at + timedelta(days=30)


async def test_updating_a_project_refreshes_updated_at_without_a_reload(
    session: AsyncSession,
) -> None:
    project = new_project(await saved_user(session))
    session.add(project)
    await session.flush()
    old = datetime(2020, 1, 1, tzinfo=UTC)
    project.updated_at = old
    await session.flush()
    assert project.updated_at == old

    project.title = "바뀐 제목"
    await session.flush()

    assert project.updated_at > old


async def test_title_is_required(session: AsyncSession) -> None:
    user = await saved_user(session)
    session.add(Project(user_id=user.id))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_title_cannot_be_empty(session: AsyncSession) -> None:
    session.add(new_project(await saved_user(session), ""))
    with pytest.raises(IntegrityError, match="title_min_length"):
        await session.flush()


async def test_title_is_limited_to_255_characters(session: AsyncSession) -> None:
    user = await saved_user(session)
    session.add(new_project(user, "가" * 255))
    await session.flush()
    session.add(new_project(user, "가" * 256))
    with pytest.raises(DBAPIError):
        await session.flush()


async def test_deletion_status_only_accepts_the_two_known_values(session: AsyncSession) -> None:
    session.add(new_project(await saved_user(session), deletion_status="purged"))
    with pytest.raises(IntegrityError, match="projects_deletion_status_check"):
        await session.flush()


async def test_user_id_is_required(session: AsyncSession) -> None:
    session.add(Project(title="주인 없음"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_project_must_belong_to_an_existing_user(session: AsyncSession) -> None:
    session.add(Project(user_id=uuid.uuid4(), title="유령 사용자"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_can_have_many_projects_and_load_them_explicitly(session: AsyncSession) -> None:
    user = await saved_user(session)
    other = await saved_user(session, "other@example.com")
    session.add_all([new_project(user, "A"), new_project(user, "B"), new_project(other, "C")])
    await session.flush()
    session.expunge_all()

    loaded = (
        await session.execute(
            select(User)
            .where(User.email == "student@example.com")
            .options(selectinload(User.projects))
        )
    ).scalar_one()

    assert sorted(p.title for p in loaded.projects) == ["A", "B"]


async def test_project_can_load_its_user_explicitly(session: AsyncSession) -> None:
    session.add(new_project(await saved_user(session)))
    await session.flush()
    session.expunge_all()

    project = (
        await session.execute(select(Project).options(selectinload(Project.user)))
    ).scalar_one()

    assert project.user.email == "student@example.com"


async def test_relationships_must_be_loaded_explicitly_in_async_code(session: AsyncSession) -> None:
    session.add(new_project(await saved_user(session)))
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(User))).scalar_one()

    with pytest.raises(InvalidRequestError):
        _ = stored.projects


async def test_deleting_a_user_deletes_its_projects(session: AsyncSession) -> None:
    user = await saved_user(session)
    other = await saved_user(session, "other@example.com")
    session.add_all([new_project(user, "A"), new_project(user, "B"), new_project(other, "C")])
    await session.flush()

    await session.delete(user)
    await session.flush()

    assert (await session.execute(select(Project.title))).scalars().all() == ["C"]


async def test_removing_a_project_from_the_user_deletes_the_row(session: AsyncSession) -> None:
    user = await saved_user(session)
    session.add_all([new_project(user, "A"), new_project(user, "B")])
    await session.flush()
    session.expunge_all()
    loaded = (await session.execute(select(User).options(selectinload(User.projects)))).scalar_one()

    loaded.projects.remove(loaded.projects[0])
    await session.flush()

    assert await count_projects(session) == 1


def test_model_matches_the_migrated_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table = cast(Table, Project.__table__)

    db_columns = {c["name"]: c for c in inspector.get_columns("projects")}
    assert set(db_columns) == set(table.c.keys())
    for model_column in table.c:
        db_column = db_columns[model_column.name]
        assert db_column["nullable"] == model_column.nullable, model_column.name
        db_length = getattr(db_column["type"], "length", None)
        assert db_length == getattr(model_column.type, "length", None), model_column.name

    assert str(db_columns["id"]["default"]).startswith("gen_random_uuid()")
    for name in ("created_at", "updated_at", "last_activity_at"):
        assert "CURRENT_TIMESTAMP" in str(db_columns[name]["default"]), name
    assert "'active'" in str(db_columns["deletion_status"]["default"])
    for name in ("description", "trashed_at", "scheduled_deletion_at", "title", "user_id"):
        assert db_columns[name]["default"] is None, name

    assert inspector.get_pk_constraint("projects")["constrained_columns"] == ["id"]

    (foreign_key,) = inspector.get_foreign_keys("projects")
    assert foreign_key["constrained_columns"] == ["user_id"]
    assert foreign_key["referred_table"] == "users"
    assert foreign_key["referred_columns"] == ["id"]
    assert foreign_key["options"]["ondelete"] == "CASCADE"

    db_indexes = {i["name"]: i for i in inspector.get_indexes("projects")}
    for index in table.indexes:
        assert db_indexes[index.name]["column_names"] == [c.name for c in index.columns]
    assert set(db_indexes) == {i.name for i in table.indexes}
    assert (
        "deletion_status"
        in db_indexes["idx_projects_user_active"]["dialect_options"]["postgresql_where"]
    )
    assert "postgresql_where" not in db_indexes["idx_projects_user_id"]["dialect_options"]

    db_checks = {c["name"]: c["sqltext"] for c in inspector.get_check_constraints("projects")}
    model_checks = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert model_checks == set(db_checks) == {"title_min_length", "projects_deletion_status_check"}
