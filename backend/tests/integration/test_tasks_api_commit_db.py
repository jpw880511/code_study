"""The task endpoints with the real get_session: the work is committed before the response.

A different session then reads the result, which the shared-transaction tests cannot show.
"""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.api.dependencies import ACCESS_TOKEN_COOKIE
from src.config import AppSettings
from src.db import session as session_module
from src.db.session import create_engine, create_session_factory
from src.main import create_app
from src.models import CodeFile, Project, Task, UploadedCode, User
from src.utils.jwt import JWTSettings, create_access_token, get_jwt_settings

SETTINGS = JWTSettings(  # type: ignore[call-arg]
    _env_file=None, secret_key="a" * 40, refresh_secret_key="r" * 40
)
FORM = {
    "title": "계산기 함수 학습",
    "upload_method": "paste",
    "code": "print(1)\n",
    "language": "python",
}


@pytest.fixture
async def factory(
    test_database_url: str, migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(test_database_url)
    created = create_session_factory(engine)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: created)
    yield created
    async with created() as cleanup:
        await cleanup.execute(delete(User))  # projects, tasks and uploads follow (CASCADE)
        await cleanup.commit()
    await engine.dispose()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
async def client(
    factory: async_sessionmaker[AsyncSession], root: Path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(
        AppSettings(_env_file=None, upload_storage_path=root)  # type: ignore[call-arg]
    )
    app.dependency_overrides[get_jwt_settings] = lambda: SETTINGS
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
async def user(factory: async_sessionmaker[AsyncSession]) -> User:
    async with factory() as db:
        created = User(email="student@example.com", password_hash="$2b$12$hash")
        db.add(created)
        await db.commit()
    return created


async def call(client: httpx.AsyncClient, method: str, path: str, user: User, **kw: Any) -> Any:
    client.cookies.clear()
    token = create_access_token(str(user.id), settings=SETTINGS)
    client.cookies.set(ACCESS_TOKEN_COOKIE, token, path="/")
    return await client.request(method, f"/api/v1{path}", **kw)


async def new_project(client: httpx.AsyncClient, user: User) -> str:
    response = await call(client, "POST", "/projects", user, json={"title": "프로젝트"})
    return str(response.json()["id"])


async def count(factory: async_sessionmaker[AsyncSession], model: type) -> int:
    async with factory() as db:
        return len((await db.execute(select(model))).all())


async def test_a_created_task_is_committed_with_its_upload_and_files(
    client: httpx.AsyncClient, factory: async_sessionmaker[AsyncSession], root: Path, user: User
) -> None:
    project_id = await new_project(client, user)

    response = await call(client, "POST", f"/projects/{project_id}/tasks", user, data=FORM)

    assert response.status_code == 201
    async with factory() as other:
        task = (await other.execute(select(Task))).scalar_one()
        upload = (await other.execute(select(UploadedCode))).scalar_one()
        code_file = (await other.execute(select(CodeFile))).scalar_one()
    assert (str(task.id), task.task_number, task.deletion_status) == (
        response.json()["id"],
        1,
        "active",
    )
    assert upload.task_id == task.id and code_file.uploaded_code_id == upload.id
    assert (root / code_file.storage_path).read_bytes() == b"print(1)\n"
    read_back = await call(client, "GET", f"/tasks/{task.id}/code", user)
    assert read_back.json()["files"][0]["content"] == "print(1)\n"


async def test_a_refused_upload_commits_nothing(
    client: httpx.AsyncClient, factory: async_sessionmaker[AsyncSession], root: Path, user: User
) -> None:
    project_id = await new_project(client, user)

    response = await call(
        client, "POST", f"/projects/{project_id}/tasks", user, data={**FORM, "language": "rust"}
    )

    assert response.status_code == 422
    assert [await count(factory, m) for m in (Task, UploadedCode, CodeFile)] == [0, 0, 0]
    assert not root.exists() or list(root.rglob("*")) == []


async def test_patch_and_delete_are_committed(
    client: httpx.AsyncClient, factory: async_sessionmaker[AsyncSession], user: User
) -> None:
    project_id = await new_project(client, user)
    task_id = (await call(client, "POST", f"/projects/{project_id}/tasks", user, data=FORM)).json()[
        "id"
    ]

    await call(client, "PATCH", f"/tasks/{task_id}", user, json={"title": "바뀐 제목입니다"})
    async with factory() as other:
        row = (await other.execute(select(Task))).scalar_one()
    assert row.title == "바뀐 제목입니다"

    assert (await call(client, "DELETE", f"/tasks/{task_id}", user)).status_code == 204
    async with factory() as other:
        row = (await other.execute(select(Task))).scalar_one()
    assert (row.deletion_status, row.trashed_at is not None) == ("trashed", True)


async def test_deleting_a_project_commits_its_tasks_into_the_trash(
    client: httpx.AsyncClient, factory: async_sessionmaker[AsyncSession], user: User
) -> None:
    project_id = await new_project(client, user)
    await call(client, "POST", f"/projects/{project_id}/tasks", user, data=FORM)

    assert (await call(client, "DELETE", f"/projects/{project_id}", user)).status_code == 204

    async with factory() as other:
        task = (await other.execute(select(Task))).scalar_one()
        project = (
            await other.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
        ).scalar_one()
    assert task.deletion_status == "trashed"
    assert task.trashed_at == project.trashed_at
    assert task.scheduled_deletion_at == project.scheduled_deletion_at
