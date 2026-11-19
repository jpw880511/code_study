import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Project, Task, User
from src.services.project_errors import (
    InvalidProjectDescriptionError,
    InvalidProjectTitleError,
    ProjectForbiddenError,
    ProjectNotFoundError,
)
from src.services.project_service import ProjectService
from src.services.task_service import TaskService

OLD = datetime(2020, 1, 1, tzinfo=UTC)


async def saved_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


async def stored(session: AsyncSession, project_id: uuid.UUID) -> Project:
    """The row as the database has it (not the cached object)."""
    session.expunge_all()
    return (await session.execute(select(Project).where(Project.id == project_id))).scalar_one()


async def set_columns(session: AsyncSession, project_id: uuid.UUID, **values: object) -> None:
    await session.execute(update(Project).where(Project.id == project_id).values(**values))
    session.expunge_all()


# --- create --------------------------------------------------------------------------------


async def test_create_stores_a_project_owned_by_the_user(session: AsyncSession) -> None:
    user = await saved_user(session)

    project = await ProjectService(session).create(user.id, "내 프로젝트", "설명입니다")

    row = await stored(session, project.id)
    assert row.user_id == user.id
    assert row.title == "내 프로젝트"
    assert row.description == "설명입니다"
    assert row.deletion_status == "active"
    assert row.trashed_at is None
    assert row.scheduled_deletion_at is None


async def test_create_trims_the_title_and_description(session: AsyncSession) -> None:
    user = await saved_user(session)

    project = await ProjectService(session).create(user.id, "  제목 \n", "  설명  ")

    assert (project.title, project.description) == ("제목", "설명")


async def test_create_without_a_description_stores_null(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)

    assert (await service.create(user.id, "A")).description is None
    assert (await service.create(user.id, "B", None)).description is None
    assert (await service.create(user.id, "C", "   ")).description is None


async def test_create_sets_last_activity_to_the_creation_time(session: AsyncSession) -> None:
    user = await saved_user(session)

    project = await ProjectService(session).create(user.id, "활동")

    assert project.last_activity_at == project.created_at
    assert abs(project.created_at - datetime.now(UTC)) < timedelta(minutes=1)


@pytest.mark.parametrize("title", ["", "   ", "\n"])
async def test_create_refuses_a_blank_title_and_stores_nothing(
    session: AsyncSession, title: str
) -> None:
    user = await saved_user(session)
    service = ProjectService(session)

    with pytest.raises(InvalidProjectTitleError):
        await service.create(user.id, title)

    assert await service.list(user.id) == []


async def test_create_refuses_a_too_long_title_and_description(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)

    with pytest.raises(InvalidProjectTitleError):
        await service.create(user.id, "a" * 256)
    with pytest.raises(InvalidProjectDescriptionError):
        await service.create(user.id, "ok", "a" * 2001)

    assert await service.list(user.id) == []


async def test_create_accepts_the_maximum_lengths(session: AsyncSession) -> None:
    user = await saved_user(session)

    project = await ProjectService(session).create(user.id, "가" * 255, "나" * 2000)

    row = await stored(session, project.id)
    assert (len(row.title), len(row.description or "")) == (255, 2000)


async def test_create_stores_special_characters_literally(session: AsyncSession) -> None:
    user = await saved_user(session)
    title = "'; DROP TABLE projects; -- <script>alert(1)</script> 😀"

    project = await ProjectService(session).create(user.id, title)

    assert (await stored(session, project.id)).title == title


# --- get / list ----------------------------------------------------------------------------


async def test_get_returns_the_owners_project(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    created = await service.create(user.id, "찾기")

    found = await service.get(user.id, created.id)

    assert found.id == created.id
    assert found.title == "찾기"


async def test_list_returns_only_the_users_active_projects(session: AsyncSession) -> None:
    user = await saved_user(session)
    other = await saved_user(session, "other@example.com")
    service = ProjectService(session)
    mine = await service.create(user.id, "내 것")
    trashed = await service.create(user.id, "휴지통")
    await service.create(other.id, "남의 것")
    await service.soft_delete(user.id, trashed.id)

    result = await service.list(user.id)

    assert [p.id for p in result] == [mine.id]


async def test_list_is_empty_for_a_user_without_projects(session: AsyncSession) -> None:
    user = await saved_user(session)
    other = await saved_user(session, "other@example.com")
    await ProjectService(session).create(other.id, "남의 것")

    assert await ProjectService(session).list(user.id) == []


async def test_list_orders_by_last_activity_then_creation_time_newest_first(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    a = await service.create(user.id, "a")
    b = await service.create(user.id, "b")
    c = await service.create(user.id, "c")
    d = await service.create(user.id, "d")
    day = timedelta(days=1)
    await set_columns(session, a.id, last_activity_at=OLD + 3 * day, created_at=OLD)
    await set_columns(session, b.id, last_activity_at=OLD + 5 * day, created_at=OLD)
    # c and d tie on activity: the newer creation time comes first.
    await set_columns(session, c.id, last_activity_at=OLD + day, created_at=OLD + day)
    await set_columns(session, d.id, last_activity_at=OLD + day, created_at=OLD + 2 * day)

    result = await service.list(user.id)

    assert [p.title for p in result] == ["b", "a", "d", "c"]


async def test_list_puts_a_project_without_last_activity_last(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    never = await service.create(user.id, "never")
    seen = await service.create(user.id, "seen")
    await set_columns(session, never.id, last_activity_at=None)
    await set_columns(session, seen.id, last_activity_at=OLD)

    assert [p.title for p in await service.list(user.id)] == ["seen", "never"]


# --- update --------------------------------------------------------------------------------


async def test_update_changes_only_the_given_fields(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "원래 제목", "원래 설명")

    changed = await service.update(user.id, project.id, title="  새 제목 ")
    assert (changed.title, changed.description) == ("새 제목", "원래 설명")

    changed = await service.update(user.id, project.id, description=" 새 설명 ")
    assert (changed.title, changed.description) == ("새 제목", "새 설명")

    row = await stored(session, project.id)
    assert (row.title, row.description) == ("새 제목", "새 설명")


async def test_update_with_an_explicit_none_description_clears_it(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "제목", "설명")

    changed = await service.update(user.id, project.id, description=None)

    assert changed.description is None
    assert (await stored(session, project.id)).description is None


async def test_update_with_a_blank_description_clears_it(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "제목", "설명")

    assert (await service.update(user.id, project.id, description="  ")).description is None


async def test_update_refuses_a_none_or_blank_title_and_changes_nothing(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "제목", "설명")

    with pytest.raises(InvalidProjectTitleError):
        await service.update(user.id, project.id, title=None)
    with pytest.raises(InvalidProjectTitleError):
        await service.update(user.id, project.id, title="   ")
    with pytest.raises(InvalidProjectDescriptionError):
        await service.update(user.id, project.id, title="새 제목", description="a" * 2001)

    row = await stored(session, project.id)
    assert (row.title, row.description) == ("제목", "설명")


async def test_update_touches_updated_at_but_not_last_activity(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "제목")
    await set_columns(session, project.id, updated_at=OLD, last_activity_at=OLD)

    changed = await service.update(user.id, project.id, title="새 제목")

    assert changed.updated_at > OLD
    assert changed.last_activity_at == OLD
    row = await stored(session, project.id)
    assert row.updated_at > OLD
    assert row.last_activity_at == OLD


async def test_update_without_changes_returns_the_project_untouched(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "제목")
    await set_columns(session, project.id, updated_at=OLD)

    unchanged = await service.update(user.id, project.id)

    assert unchanged.title == "제목"
    assert (await stored(session, project.id)).updated_at == OLD


async def test_update_to_the_same_values_does_not_touch_updated_at(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "제목", "설명")
    await set_columns(session, project.id, updated_at=OLD)

    await service.update(user.id, project.id, title="제목", description="설명")

    assert (await stored(session, project.id)).updated_at == OLD


# --- soft delete ---------------------------------------------------------------------------


async def test_soft_delete_marks_the_project_trashed_for_30_days(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "버릴 것")
    before = datetime.now(UTC)

    await service.soft_delete(user.id, project.id)

    after = datetime.now(UTC)
    row = await stored(session, project.id)
    assert row.deletion_status == "trashed"
    assert row.trashed_at is not None and row.scheduled_deletion_at is not None
    assert before <= row.trashed_at <= after
    assert row.scheduled_deletion_at - row.trashed_at == timedelta(days=30)
    assert row.title == "버릴 것"  # the row is kept, not deleted


async def test_soft_deleted_project_disappears_from_get_and_list(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "버릴 것")

    await service.soft_delete(user.id, project.id)

    assert await service.list(user.id) == []
    with pytest.raises(ProjectNotFoundError):
        await service.get(user.id, project.id)


async def test_soft_delete_only_affects_the_given_project(session: AsyncSession) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    keep = await service.create(user.id, "유지")
    gone = await service.create(user.id, "삭제")

    await service.soft_delete(user.id, gone.id)

    assert [p.id for p in await service.list(user.id)] == [keep.id]


# --- ownership matrix: own / foreign / missing / trashed ----------------------------------


async def run(
    service: ProjectService, action: str, user_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    if action == "get":
        await service.get(user_id, project_id)
    elif action == "update":
        await service.update(user_id, project_id, title="바꿈")
    else:
        await service.soft_delete(user_id, project_id)


@pytest.mark.parametrize("action", ["get", "update", "delete"])
async def test_own_project_is_allowed(session: AsyncSession, action: str) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "내 것")

    await run(service, action, user.id, project.id)


@pytest.mark.parametrize("action", ["get", "update", "delete"])
async def test_a_foreign_active_project_is_forbidden_and_untouched(
    session: AsyncSession, action: str
) -> None:
    owner = await saved_user(session)
    intruder = await saved_user(session, "intruder@example.com")
    service = ProjectService(session)
    project = await service.create(owner.id, "비밀 프로젝트", "비밀 설명")

    with pytest.raises(ProjectForbiddenError) as caught:
        await run(service, action, intruder.id, project.id)

    assert "비밀" not in caught.value.message
    assert "비밀" not in repr(caught.value.args)
    row = await stored(session, project.id)
    assert (row.title, row.description, row.deletion_status) == (
        "비밀 프로젝트",
        "비밀 설명",
        "active",
    )


@pytest.mark.parametrize("action", ["get", "update", "delete"])
async def test_a_missing_project_is_not_found(session: AsyncSession, action: str) -> None:
    user = await saved_user(session)

    with pytest.raises(ProjectNotFoundError):
        await run(ProjectService(session), action, user.id, uuid.uuid4())


@pytest.mark.parametrize("action", ["get", "update", "delete"])
async def test_a_trashed_project_is_not_found_for_its_owner(
    session: AsyncSession, action: str
) -> None:
    user = await saved_user(session)
    service = ProjectService(session)
    project = await service.create(user.id, "버려짐")
    await service.soft_delete(user.id, project.id)

    with pytest.raises(ProjectNotFoundError):
        await run(service, action, user.id, project.id)


@pytest.mark.parametrize("action", ["get", "update", "delete"])
async def test_a_trashed_project_is_not_found_for_others_too_so_nothing_leaks(
    session: AsyncSession, action: str
) -> None:
    owner = await saved_user(session)
    other = await saved_user(session, "other@example.com")
    service = ProjectService(session)
    project = await service.create(owner.id, "버려짐")
    await service.soft_delete(owner.id, project.id)

    with pytest.raises(ProjectNotFoundError):
        await run(service, action, other.id, project.id)


async def test_not_found_and_forbidden_errors_carry_no_project_data(
    session: AsyncSession,
) -> None:
    owner = await saved_user(session)
    other = await saved_user(session, "other@example.com")
    service = ProjectService(session)
    project = await service.create(owner.id, "유일한 제목", "유일한 설명")

    with pytest.raises(ProjectForbiddenError) as forbidden:
        await service.get(other.id, project.id)
    with pytest.raises(ProjectNotFoundError) as missing:
        await service.get(other.id, uuid.uuid4())

    for error in (forbidden.value, missing.value):
        text = f"{error.message} {error!r} {error.args}"
        assert "유일한" not in text
        assert str(project.id) not in text
        assert str(owner.id) not in text


async def test_validation_runs_after_the_ownership_check_for_updates(
    session: AsyncSession,
) -> None:
    owner = await saved_user(session)
    other = await saved_user(session, "other@example.com")
    service = ProjectService(session)
    project = await service.create(owner.id, "제목")

    with pytest.raises(ProjectForbiddenError):
        await service.update(other.id, project.id, title="")


# --- soft delete sends the project's tasks to the trash too (FR-009D) ----------------------


async def test_soft_delete_trashes_the_active_tasks_with_the_projects_timestamps(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    project = await ProjectService(session).create(user.id, "버릴 것")
    tasks = TaskService(session)
    first = await tasks.create(user.id, project.id, "첫 번째 태스크")
    second = await tasks.create(user.id, project.id, "두 번째 태스크")

    await ProjectService(session).soft_delete(user.id, project.id)

    session.expunge_all()
    row = await stored(session, project.id)
    for task_id in (first.id, second.id):
        task = (await session.execute(select(Task).where(Task.id == task_id))).scalar_one()
        assert task.deletion_status == "trashed"
        assert task.trashed_at == row.trashed_at
        assert task.scheduled_deletion_at == row.scheduled_deletion_at


async def test_soft_delete_keeps_the_earlier_trash_time_of_an_already_trashed_task(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    project = await ProjectService(session).create(user.id, "버릴 것")
    tasks = TaskService(session)
    earlier = await tasks.create(user.id, project.id, "먼저 지운 태스크")
    await tasks.soft_delete(user.id, earlier.id)
    session.expunge_all()
    first_trashed_at = (
        await session.execute(select(Task.trashed_at).where(Task.id == earlier.id))
    ).scalar_one()

    await ProjectService(session).soft_delete(user.id, project.id)

    session.expunge_all()
    after = (
        await session.execute(select(Task.trashed_at).where(Task.id == earlier.id))
    ).scalar_one()
    assert after == first_trashed_at


async def test_soft_delete_leaves_the_tasks_of_other_projects_alone(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    projects = ProjectService(session)
    gone = await projects.create(user.id, "삭제")
    kept = await projects.create(user.id, "유지")
    tasks = TaskService(session)
    survivor = await tasks.create(user.id, kept.id, "살아남는 태스크")

    await projects.soft_delete(user.id, gone.id)

    session.expunge_all()
    row = (await session.execute(select(Task).where(Task.id == survivor.id))).scalar_one()
    assert (row.deletion_status, row.trashed_at) == ("active", None)
    assert [t.id for t in await tasks.list(user.id, kept.id)] == [survivor.id]
