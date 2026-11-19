"""When the job is queued: after the commit, never before, never after a rollback."""

import logging
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.api.dependencies import ACCESS_TOKEN_COOKIE
from src.config import AppSettings
from src.main import create_app
from src.models import User
from src.services.document.document_queue_service import ENQUEUE_FAILED_MESSAGE
from src.tasks import document_generation
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
async def client(
    committed_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(
        AppSettings(_env_file=None, upload_storage_path=tmp_path / "uploads")  # type: ignore[call-arg]
    )
    app.dependency_overrides[get_jwt_settings] = lambda: SETTINGS
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
async def user(committed_factory: async_sessionmaker[AsyncSession]) -> User:
    async with committed_factory() as db:
        created = User(email="student@example.com", password_hash="$2b$12$hash")
        db.add(created)
        await db.commit()
    return created


async def call(client: httpx.AsyncClient, method: str, path: str, user: User, **kw: Any) -> Any:
    client.cookies.clear()
    token = create_access_token(str(user.id), settings=SETTINGS)
    client.cookies.set(ACCESS_TOKEN_COOKIE, token, path="/")
    return await client.request(method, f"/api/v1{path}", **kw)


@pytest.fixture
async def project_id(client: httpx.AsyncClient, user: User) -> str:
    response = await call(client, "POST", "/projects", user, json={"title": "프로젝트"})
    return str(response.json()["id"])


def rows(engine: Engine, query: str, **params: Any) -> list[Any]:
    with engine.connect() as connection:  # another connection: only committed data is visible
        return list(connection.execute(text(query), params))


async def test_the_job_is_sent_after_the_commit_with_the_prepared_job_id(
    client: httpx.AsyncClient,
    user: User,
    project_id: str,
    migrated_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visible: list[Any] = []

    def send(task_id: str, job_id: str) -> None:
        # What a worker would see the moment it receives the message.
        found = rows(
            migrated_engine,
            "SELECT d.generation_status, d.celery_task_id FROM learning_documents d "
            "JOIN tasks t ON t.id = d.task_id WHERE t.id = :id",
            id=uuid.UUID(task_id),
        )
        visible.append((task_id, job_id, found))

    monkeypatch.setattr(document_generation, "enqueue_generation", send)
    response = await call(client, "POST", f"/projects/{project_id}/tasks", user, data=FORM)
    assert response.status_code == 201
    task_id = response.json()["id"]
    assert visible == [(task_id, visible[0][1], [("pending", visible[0][1])])]
    assert "document" not in response.text  # the response did not change


async def test_a_refused_upload_sends_nothing_and_leaves_no_document(
    client: httpx.AsyncClient,
    user: User,
    project_id: str,
    migrated_engine: Engine,
    sent_jobs: list[tuple[str, str]],
) -> None:
    bad = {**FORM, "code": "   "}
    response = await call(client, "POST", f"/projects/{project_id}/tasks", user, data=bad)
    assert response.status_code == 422
    assert sent_jobs == []
    assert rows(migrated_engine, "SELECT 1 FROM learning_documents") == []


async def test_a_request_that_fails_after_the_document_was_made_rolls_back_and_sends_nothing(
    client: httpx.AsyncClient,
    user: User,
    project_id: str,
    migrated_engine: Engine,
    sent_jobs: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("response could not be built")

    monkeypatch.setattr("src.api.tasks.create_task_response", boom)
    response = await call(client, "POST", f"/projects/{project_id}/tasks", user, data=FORM)
    assert response.status_code == 500
    assert sent_jobs == []
    assert rows(migrated_engine, "SELECT 1 FROM learning_documents") == []
    assert rows(migrated_engine, "SELECT 1 FROM tasks") == []


async def test_a_dead_broker_does_not_fail_the_upload_and_the_document_says_failed(
    client: httpx.AsyncClient,
    user: User,
    project_id: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def send(task_id: str, job_id: str) -> None:
        raise ConnectionError("Error 111 connecting to redis://localhost:6379. Connection refused.")

    monkeypatch.setattr(document_generation, "enqueue_generation", send)
    caplog.set_level(logging.DEBUG)
    response = await call(client, "POST", f"/projects/{project_id}/tasks", user, data=FORM)
    assert response.status_code == 201
    task_id = response.json()["id"]
    status = await call(client, "GET", f"/tasks/{task_id}/document/status", user)
    assert status.status_code == 200
    assert status.json()["status"] == "failed"
    assert status.json()["error"] == ENQUEUE_FAILED_MESSAGE
    assert "localhost:6379" not in status.text
    document = await call(client, "GET", f"/tasks/{task_id}/document", user)
    assert document.json()["status"] == "failed"
    assert document.json()["content"] is None
