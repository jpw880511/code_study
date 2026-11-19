import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Project, Task, User
from src.services.project_errors import ProjectForbiddenError, ProjectNotFoundError
from src.services.project_service import ProjectService
from src.services.task_errors import (
    InvalidTaskDescriptionError,
    InvalidTaskTitleError,
    TaskForbiddenError,
    TaskNotFoundError,
)
from src.services.task_service import TaskService

OLD = datetime(2020, 1, 1, tzinfo=UTC)
TITLE = "계산기 함수 학습"


async def saved_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


async def saved_project(session: AsyncSession, user: User, title: str = "프로젝트") -> Project:
    return await ProjectService(session).create(user.id, title)


async def stored_task(session: AsyncSession, task_id: uuid.UUID) -> Task:
    session.expunge_all()
    return (await session.execute(select(Task).where(Task.id == task_id))).scalar_one()


async def stored_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    session.expunge_all()
    return (await session.execute(select(Project).where(Project.id == project_id))).scalar_one()


async def age_project(session: AsyncSession, project_id: uuid.UUID) -> None:
    """Make last_activity_at old so a bump is visible."""
    await session.execute(
        update(Project).where(Project.id == project_id).values(last_activity_at=OLD)
    )
    session.expunge_all()


# --- create --------------------------------------------------------------------------------


async def test_create_stores_an_active_task_numbered_one(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)

    task = await TaskService(session).create(user.id, project.id, TITLE, "설명", "paste")

    row = await stored_task(session, task.id)
    assert row.project_id == project.id
    assert row.task_number == 1
    assert row.title == TITLE
    assert row.description == "설명"
    assert row.upload_method == "paste"
    assert row.deletion_status == "active"
    assert (row.trashed_at, row.scheduled_deletion_at) == (None, None)


async def test_create_trims_and_normalises_the_text_fields(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)

    task = await TaskService(session).create(user.id, project.id, f"  {TITLE} \n", "   ")

    assert (task.title, task.description, task.upload_method) == (TITLE, None, None)


async def test_task_numbers_count_up_per_project(session: AsyncSession) -> None:
    user = await saved_user(session)
    first = await saved_project(session, user, "첫째")
    second = await saved_project(session, user, "둘째")
    service = TaskService(session)

    numbers = [
        (await service.create(user.id, first.id, TITLE)).task_number,
        (await service.create(user.id, first.id, TITLE)).task_number,
        (await service.create(user.id, second.id, TITLE)).task_number,
        (await service.create(user.id, first.id, TITLE)).task_number,
    ]

    assert numbers == [1, 2, 1, 3]


async def test_a_trashed_tasks_number_is_never_reused(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    await service.create(user.id, project.id, TITLE)
    last = await service.create(user.id, project.id, TITLE)
    await service.soft_delete(user.id, last.id)

    again = await service.create(user.id, project.id, TITLE)

    assert again.task_number == 3


async def test_create_moves_the_projects_last_activity_forward(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    await age_project(session, project.id)
    before = datetime.now(UTC)

    await TaskService(session).create(user.id, project.id, TITLE)

    assert (await stored_project(session, project.id)).last_activity_at >= before


@pytest.mark.parametrize("title", ["짧음", "", "   "])
async def test_create_with_a_bad_title_stores_nothing(session: AsyncSession, title: str) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)

    with pytest.raises(InvalidTaskTitleError):
        await TaskService(session).create(user.id, project.id, title)

    assert (await session.execute(select(Task))).first() is None


async def test_create_with_a_bad_description_stores_nothing(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)

    with pytest.raises(InvalidTaskDescriptionError):
        await TaskService(session).create(user.id, project.id, TITLE, "가" * 501)

    assert (await session.execute(select(Task))).first() is None


async def test_create_in_a_foreign_project_is_forbidden(session: AsyncSession) -> None:
    owner = await saved_user(session)
    stranger = await saved_user(session, "stranger@example.com")
    project = await saved_project(session, owner)

    with pytest.raises(ProjectForbiddenError):
        await TaskService(session).create(stranger.id, project.id, TITLE)


async def test_create_in_a_trashed_or_missing_project_is_not_found(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    await ProjectService(session).soft_delete(user.id, project.id)
    service = TaskService(session)

    with pytest.raises(ProjectNotFoundError):
        await service.create(user.id, project.id, TITLE)
    with pytest.raises(ProjectNotFoundError):
        await service.create(user.id, uuid.uuid4(), TITLE)


# --- get -----------------------------------------------------------------------------------


async def test_get_returns_the_task(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    created = await service.create(user.id, project.id, TITLE)

    task = await service.get(user.id, created.id)

    assert (task.id, task.title, task.task_number) == (created.id, TITLE, 1)
    assert task.uploaded_code is None  # loaded (None), not a lazy-load error


# --- list ----------------------------------------------------------------------------------


async def test_list_is_ordered_by_task_number_and_hides_trashed_tasks(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    other = await saved_project(session, user, "다른")
    service = TaskService(session)
    one = await service.create(user.id, project.id, "첫 번째 태스크")
    two = await service.create(user.id, project.id, "두 번째 태스크")
    three = await service.create(user.id, project.id, "세 번째 태스크")
    await service.create(user.id, other.id, "다른 프로젝트 태스크")
    await service.soft_delete(user.id, two.id)

    tasks = await service.list(user.id, project.id)

    assert [t.id for t in tasks] == [one.id, three.id]
    assert [t.task_number for t in tasks] == [1, 3]
    assert all(t.uploaded_code is None for t in tasks)


async def test_list_of_a_project_without_tasks_is_empty(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)

    assert await TaskService(session).list(user.id, project.id) == []


async def test_list_follows_the_project_ownership_rules(session: AsyncSession) -> None:
    owner = await saved_user(session)
    stranger = await saved_user(session, "stranger@example.com")
    project = await saved_project(session, owner)
    trashed = await saved_project(session, owner, "버림")
    await ProjectService(session).soft_delete(owner.id, trashed.id)
    service = TaskService(session)

    with pytest.raises(ProjectForbiddenError):
        await service.list(stranger.id, project.id)
    with pytest.raises(ProjectNotFoundError):
        await service.list(owner.id, trashed.id)
    with pytest.raises(ProjectNotFoundError):
        await service.list(owner.id, uuid.uuid4())


# --- update --------------------------------------------------------------------------------


async def test_update_changes_only_the_given_fields(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    task = await service.create(user.id, project.id, TITLE, "원래 설명", "file")

    await service.update(user.id, task.id, title="  새 제목입니다 ")
    row = await stored_task(session, task.id)
    assert (row.title, row.description) == ("새 제목입니다", "원래 설명")

    await service.update(user.id, task.id, description="새 설명")
    row = await stored_task(session, task.id)
    assert (row.title, row.description) == ("새 제목입니다", "새 설명")


async def test_update_with_none_clears_the_description(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    task = await service.create(user.id, project.id, TITLE, "지울 설명")

    await service.update(user.id, task.id, description=None)

    assert (await stored_task(session, task.id)).description is None


async def test_update_never_touches_the_number_or_the_upload_method(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    await service.create(user.id, project.id, TITLE)
    task = await service.create(user.id, project.id, TITLE, None, "folder")

    await service.update(user.id, task.id, title="바뀐 제목입니다", description="d")

    row = await stored_task(session, task.id)
    assert (row.task_number, row.upload_method) == (2, "folder")


async def test_update_moves_the_project_activity_forward(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    task = await service.create(user.id, project.id, TITLE)
    await age_project(session, project.id)
    before = datetime.now(UTC)

    await service.update(user.id, task.id, title="바뀐 제목입니다")

    assert (await stored_project(session, project.id)).last_activity_at >= before


async def test_update_validates_and_leaves_the_task_unchanged(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    task = await service.create(user.id, project.id, TITLE, "설명")

    with pytest.raises(InvalidTaskTitleError):
        await service.update(user.id, task.id, title="짧음", description="바뀌면 안 됨")
    with pytest.raises(InvalidTaskTitleError):
        await service.update(user.id, task.id, title=None)
    with pytest.raises(InvalidTaskDescriptionError):
        await service.update(user.id, task.id, description="가" * 501)

    row = await stored_task(session, task.id)
    assert (row.title, row.description) == (TITLE, "설명")


# --- soft delete ---------------------------------------------------------------------------


async def test_soft_delete_trashes_the_task_for_30_days_and_keeps_the_row(
    session: AsyncSession,
) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    task = await service.create(user.id, project.id, TITLE)
    before = datetime.now(UTC)

    await service.soft_delete(user.id, task.id)

    after = datetime.now(UTC)
    row = await stored_task(session, task.id)
    assert row.deletion_status == "trashed"
    assert row.trashed_at is not None and row.scheduled_deletion_at is not None
    assert before <= row.trashed_at <= after
    assert row.scheduled_deletion_at - row.trashed_at == timedelta(days=30)
    assert row.title == TITLE


async def test_soft_delete_moves_project_activity_forward(session: AsyncSession) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    task = await service.create(user.id, project.id, TITLE)
    await age_project(session, project.id)
    before = datetime.now(UTC)

    await service.soft_delete(user.id, task.id)

    assert (await stored_project(session, project.id)).last_activity_at >= before


# --- ownership matrix: own / foreign / missing / trashed -----------------------------------


async def run(service: TaskService, action: str, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
    if action == "get":
        await service.get(user_id, task_id)
    elif action == "update":
        await service.update(user_id, task_id, title="바꾼 제목입니다")
    else:
        await service.soft_delete(user_id, task_id)


@pytest.mark.parametrize("action", ["get", "update", "delete"])
async def test_own_task_is_allowed(session: AsyncSession, action: str) -> None:
    user = await saved_user(session)
    project = await saved_project(session, user)
    service = TaskService(session)
    task = await service.create(user.id, project.id, TITLE)

    await run(service, action, user.id, task.id)


@pytest.mark.parametrize("action", ["get", "update", "delete"])
async def test_foreign_task_is_forbidden_even_with_a_bad_input(
    session: AsyncSession, action: str
) -> None:
    owner = await saved_user(session)
    stranger = await saved_user(session, "stranger@example.com")
    project = await saved_project(session, owner)
    service = TaskService(session)
    task = await service.create(owner.id, project.id, TITLE)

    with pytest.raises(TaskForbiddenError):
        await run(service, action, stranger.id, task.id)
    with pytest.raises(TaskForbiddenError):
        await service.update(stranger.id, task.id, title="짧음")


@pytest.mark.parametrize("action", ["get", "update", "delete"])
async def test_missing_task_is_not_found(session: AsyncSession, action: str) -> None:
    user = await saved_user(session)

    with pytest.raises(TaskNotFoundError):
        await run(TaskService(session), action, user.id, uuid.uuid4())


@pytest.mark.parametrize("action", ["get", "update", "delete"])
@pytest.mark.parametrize("who", ["owner", "stranger"])
async def test_trashed_task_is_not_found_for_everybody(
    session: AsyncSession, action: str, who: str
) -> None:
    owner = await saved_user(session)
    stranger = await saved_user(session, "stranger@example.com")
    project = await saved_project(session, owner)
    service = TaskService(session)
    task = await service.create(owner.id, project.id, TITLE)
    await service.soft_delete(owner.id, task.id)

    with pytest.raises(TaskNotFoundError):
        await run(service, action, owner.id if who == "owner" else stranger.id, task.id)


@pytest.mark.parametrize("action", ["get", "update", "delete"])
@pytest.mark.parametrize("who", ["owner", "stranger"])
async def test_a_task_of_a_trashed_project_is_not_found_for_everybody(
    session: AsyncSession, action: str, who: str
) -> None:
    """A project trashed on its own (its tasks not touched) hides the tasks too."""
    owner = await saved_user(session)
    stranger = await saved_user(session, "stranger@example.com")
    project = await saved_project(session, owner)
    service = TaskService(session)
    task = await service.create(owner.id, project.id, TITLE)
    await session.execute(
        update(Project)
        .where(Project.id == project.id)
        .values(deletion_status="trashed", trashed_at=datetime.now(UTC))
    )
    session.expunge_all()

    with pytest.raises(TaskNotFoundError):
        await run(service, action, owner.id if who == "owner" else stranger.id, task.id)
