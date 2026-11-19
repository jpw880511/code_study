"""Builds uploaded tasks (with their pending document) for the document tests."""

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Task, User
from src.services.code_analysis.code_upload_service import CodeUploadService
from src.services.code_analysis.file_storage import FileStorage
from src.services.project_service import ProjectService

CODE = "".join(f"line{i} = {i}\n" for i in range(1, 14))  # 13 lines, as in document_fixtures


async def make_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


async def upload_task(
    session: AsyncSession, root: Path, user: User, *, code: str = CODE, project_id: object = None
) -> Task:
    """A task created through the real upload service: stored code and a pending document."""
    if project_id is None:
        project_id = (await ProjectService(session).create(user.id, "프로젝트")).id
    result = await CodeUploadService(session, FileStorage(root)).create_task(
        user.id,
        project_id,  # type: ignore[arg-type]
        title="계산기 함수 학습",
        description=None,
        upload_method="paste",
        code=code,
        language="python",
    )
    return result.task


class MemoryRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value
        self.ttls[key] = ex

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)

    async def aclose(self) -> None:
        self.closed = True


class DownRedis:
    """Every call fails the way a refused connection does, with a secret in the message."""

    async def set(self, *args: Any, **kwargs: Any) -> None:
        raise ConnectionError("redis://:topsecret@host down")

    get = delete = aclose = set
