import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import Project, Task, UploadedCode
from src.services.project_service import (
    ACTIVE,
    TRASH_RETENTION,
    TRASHED,
    UNSET,
    ProjectService,
    _Unset,
)
from src.services.task_errors import (
    InvalidTaskDescriptionError,
    InvalidTaskTitleError,
    TaskForbiddenError,
    TaskNotFoundError,
)

MIN_TITLE_LENGTH = 5
MAX_TITLE_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 500


def normalize_task_title(title: str | None) -> str:
    """Trim, and refuse a title that is too short (FR-008), too long or has a NUL character."""
    trimmed = (title or "").strip()
    if len(trimmed) < MIN_TITLE_LENGTH:
        raise InvalidTaskTitleError(f"Task 제목은 최소 {MIN_TITLE_LENGTH}자 이상이어야 합니다.")
    if len(trimmed) > MAX_TITLE_LENGTH:
        raise InvalidTaskTitleError(f"Task 제목은 최대 {MAX_TITLE_LENGTH}자까지 입력 가능합니다.")
    if "\x00" in trimmed:
        raise InvalidTaskTitleError("Task 제목에 사용할 수 없는 문자가 포함되어 있습니다.")
    return trimmed


def normalize_task_description(description: str | None) -> str | None:
    """Trim (FR-009); a blank description is stored as NULL."""
    trimmed = (description or "").strip()
    if len(trimmed) > MAX_DESCRIPTION_LENGTH:
        raise InvalidTaskDescriptionError(
            f"Task 설명은 최대 {MAX_DESCRIPTION_LENGTH}자까지 입력 가능합니다."
        )
    if "\x00" in trimmed:
        raise InvalidTaskDescriptionError("Task 설명에 사용할 수 없는 문자가 포함되어 있습니다.")
    return trimmed or None


class TaskService:
    """The tasks of a user's projects. It never commits: the request's session does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        title: str | None,
        description: str | None = None,
        upload_method: str | None = None,
    ) -> Task:
        """Create the next task of a project (numbers are never reused, trashed tasks count)."""
        projects = ProjectService(self.session)
        await projects.get(user_id, project_id)
        clean_title = normalize_task_title(title)
        clean_description = normalize_task_description(description)
        await self._lock_project(project_id)
        # The row was re-read under the lock: it may have been trashed while this request waited.
        project = await projects.get(user_id, project_id)
        number = (
            await self.session.execute(
                select(func.coalesce(func.max(Task.task_number), 0) + 1).where(
                    Task.project_id == project_id
                )
            )
        ).scalar_one()
        task = Task(
            id=uuid.uuid4(),
            project_id=project_id,
            task_number=number,
            title=clean_title,
            description=clean_description,
            upload_method=upload_method,
            deletion_status=ACTIVE,
        )
        self.session.add(task)
        project.last_activity_at = datetime.now(UTC)
        await self.session.flush()
        return task

    async def get(self, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
        """The task with its upload and files loaded."""
        task, _ = await self._owned_active_task(user_id, task_id)
        return task

    async def list(self, user_id: uuid.UUID, project_id: uuid.UUID) -> list[Task]:
        """The project's active tasks by task number, each with its upload summary loaded."""
        await ProjectService(self.session).get(user_id, project_id)
        result = await self.session.execute(
            select(Task)
            .where(Task.project_id == project_id, Task.deletion_status == ACTIVE)
            .order_by(Task.task_number)
            .options(selectinload(Task.uploaded_code))
            .execution_options(populate_existing=True)
        )
        return list(result.scalars())

    async def update(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        *,
        title: str | None | _Unset = UNSET,
        description: str | None | _Unset = UNSET,
    ) -> Task:
        """Change only the given fields; the number and the upload never change."""
        task, project = await self._owned_active_task(user_id, task_id)
        new_title = task.title if isinstance(title, _Unset) else normalize_task_title(title)
        new_description = (
            task.description
            if isinstance(description, _Unset)
            else normalize_task_description(description)
        )
        task.title = new_title
        task.description = new_description
        project.last_activity_at = datetime.now(UTC)
        await self.session.flush()
        return task

    async def soft_delete(self, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
        """Move the task to the trash for 30 days. Its files stay on disk until the purge."""
        task, project = await self._owned_active_task(user_id, task_id)
        trashed_at = datetime.now(UTC)
        task.deletion_status = TRASHED
        task.trashed_at = trashed_at
        task.scheduled_deletion_at = trashed_at + TRASH_RETENTION
        project.last_activity_at = trashed_at
        await self.session.flush()

    async def _lock_project(self, project_id: uuid.UUID) -> None:
        """Lock the project row so two creators cannot compute the same task number."""
        await self.session.execute(
            select(Project)
            .where(Project.id == project_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def _owned_active_task(
        self, user_id: uuid.UUID, task_id: uuid.UUID
    ) -> tuple[Task, Project]:
        """The one ownership check. Trashed tasks, and tasks of trashed projects, are 404."""
        row = (
            await self.session.execute(
                select(Task, Project)
                .join(Project, Task.project_id == Project.id)
                .where(Task.id == task_id)
                .options(selectinload(Task.uploaded_code).selectinload(UploadedCode.code_files))
                .execution_options(populate_existing=True)
            )
        ).first()
        if row is None:
            raise TaskNotFoundError()
        task, project = row
        if task.deletion_status != ACTIVE or project.deletion_status != ACTIVE:
            raise TaskNotFoundError()
        if project.user_id != user_id:
            raise TaskForbiddenError()
        return task, project
