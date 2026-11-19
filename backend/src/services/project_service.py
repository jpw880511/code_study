import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Project, Task
from src.services.project_errors import (
    InvalidProjectDescriptionError,
    InvalidProjectTitleError,
    ProjectForbiddenError,
    ProjectNotFoundError,
)

MAX_TITLE_LENGTH = 255
# Our own safety limit: the database column is unbounded TEXT.
MAX_DESCRIPTION_LENGTH = 2000
TRASH_RETENTION = timedelta(days=30)
ACTIVE = "active"
TRASHED = "trashed"


class _Unset(Enum):
    UNSET = "unset"


# "Leave this field alone" for update(); None is a real value (it clears the description).
UNSET = _Unset.UNSET


def normalize_title(title: str | None) -> str:
    """Trim, and refuse an empty, too long or NUL-containing (PostgreSQL rejects it) title."""
    trimmed = (title or "").strip()
    if not trimmed:
        raise InvalidProjectTitleError("프로젝트 제목은 최소 1자 이상이어야 합니다.")
    if len(trimmed) > MAX_TITLE_LENGTH:
        raise InvalidProjectTitleError(
            f"프로젝트 제목은 최대 {MAX_TITLE_LENGTH}자까지 입력 가능합니다."
        )
    if "\x00" in trimmed:
        raise InvalidProjectTitleError("프로젝트 제목에 사용할 수 없는 문자가 포함되어 있습니다.")
    return trimmed


def normalize_description(description: str | None) -> str | None:
    """Trim; an empty description is stored as NULL."""
    trimmed = (description or "").strip()
    if len(trimmed) > MAX_DESCRIPTION_LENGTH:
        raise InvalidProjectDescriptionError(
            f"프로젝트 설명은 최대 {MAX_DESCRIPTION_LENGTH}자까지 입력 가능합니다."
        )
    if "\x00" in trimmed:
        raise InvalidProjectDescriptionError(
            "프로젝트 설명에 사용할 수 없는 문자가 포함되어 있습니다."
        )
    return trimmed or None


class ProjectService:
    """A user's projects. It never commits: the request's session does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, user_id: uuid.UUID, title: str | None, description: str | None = None
    ) -> Project:
        project = Project(
            user_id=user_id,
            title=normalize_title(title),
            description=normalize_description(description),
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def get(self, user_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        return await self._owned_active_project(user_id, project_id)

    async def list(self, user_id: uuid.UUID) -> list[Project]:
        result = await self.session.execute(
            select(Project)
            .where(Project.user_id == user_id, Project.deletion_status == ACTIVE)
            .order_by(Project.last_activity_at.desc().nulls_last(), Project.created_at.desc())
        )
        return list(result.scalars())

    async def update(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        *,
        title: str | None | _Unset = UNSET,
        description: str | None | _Unset = UNSET,
    ) -> Project:
        """Change only the given fields. last_activity_at is about tasks, so it stays."""
        project = await self._owned_active_project(user_id, project_id)
        new_title = project.title if isinstance(title, _Unset) else normalize_title(title)
        new_description = (
            project.description
            if isinstance(description, _Unset)
            else normalize_description(description)
        )
        project.title = new_title
        project.description = new_description
        await self.session.flush()
        return project

    async def soft_delete(self, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
        """Trash the project and its active tasks together, with the same times (FR-009D)."""
        project = await self._owned_active_project(user_id, project_id)
        trashed_at = datetime.now(UTC)
        scheduled_deletion_at = trashed_at + TRASH_RETENTION
        project.deletion_status = TRASHED
        project.trashed_at = trashed_at
        project.scheduled_deletion_at = scheduled_deletion_at
        # Tasks trashed earlier keep their own (earlier) times.
        await self.session.execute(
            update(Task)
            .where(Task.project_id == project_id, Task.deletion_status == ACTIVE)
            .values(
                deletion_status=TRASHED,
                trashed_at=trashed_at,
                scheduled_deletion_at=scheduled_deletion_at,
            )
        )
        await self.session.flush()

    async def _owned_active_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        """The one ownership check. Trashed projects do not exist for anybody (404, not 403)."""
        project = await self.session.get(Project, project_id)
        if project is None or project.deletion_status != ACTIVE:
            raise ProjectNotFoundError()
        if project.user_id != user_id:
            raise ProjectForbiddenError()
        return project
