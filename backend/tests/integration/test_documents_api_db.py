import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies import ACCESS_TOKEN_COOKIE, get_notice_store
from src.config import AppSettings
from src.db.session import get_session
from src.main import create_app
from src.models import LearningDocument, User
from src.services.document.document_notice_store import NoticeStore
from src.services.document.document_queue_service import STALE_MESSAGE
from src.utils.jwt import JWTSettings, create_access_token, get_jwt_settings
from tests.document_fixtures import valid_doc
from tests.queue_helpers import DownRedis, MemoryRedis

SETTINGS = JWTSettings(  # type: ignore[call-arg]
    _env_file=None, secret_key="a" * 40, refresh_secret_key="r" * 40
)
API = "/api/v1"
STATUS_KEYS = {
    "status",
    "generation_started_at",
    "generation_completed_at",
    "elapsed_seconds",
    "estimated_total_seconds",
    "notice",
    "error",
}
DOCUMENT_KEYS = {
    "task_id",
    "status",
    "content",
    "generation_started_at",
    "generation_completed_at",
    "error",
    "created_at",
    "updated_at",
}
FORM = {
    "title": "계산기 함수 학습",
    "upload_method": "paste",
    "code": "x = 1\n" * 13,
    "language": "python",
}
DOCUMENT_NOT_FOUND = {
    "error": "document_not_found",
    "message": "이 Task에는 아직 학습 문서가 없습니다.",
}


@pytest.fixture
def redis_fake() -> MemoryRedis:
    return MemoryRedis()


@pytest.fixture
def app(session: AsyncSession, tmp_path: Path, redis_fake: MemoryRedis) -> FastAPI:
    created = create_app(
        AppSettings(_env_file=None, upload_storage_path=tmp_path / "uploads")  # type: ignore[call-arg]
    )

    async def use_test_session() -> AsyncIterator[AsyncSession]:
        yield session

    created.dependency_overrides[get_session] = use_test_session
    created.dependency_overrides[get_jwt_settings] = lambda: SETTINGS
    created.dependency_overrides[get_notice_store] = lambda: NoticeStore(redis_fake)
    return created


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def make_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def user(session: AsyncSession) -> User:
    return await make_user(session)


@pytest.fixture
async def other(session: AsyncSession) -> User:
    return await make_user(session, "other@example.com")


async def call(
    client: httpx.AsyncClient, method: str, path: str, user: User | None = None, **kw: Any
) -> httpx.Response:
    client.cookies.clear()
    if user is not None:
        token = create_access_token(str(user.id), settings=SETTINGS)
        client.cookies.set(ACCESS_TOKEN_COOKIE, token, path="/")
    return await client.request(method, f"{API}{path}", **kw)


@pytest.fixture
async def project_id(client: httpx.AsyncClient, user: User) -> str:
    response = await call(client, "POST", "/projects", user, json={"title": "프로젝트"})
    return str(response.json()["id"])


@pytest.fixture
async def task_id(client: httpx.AsyncClient, user: User, project_id: str) -> str:
    response = await call(client, "POST", f"/projects/{project_id}/tasks", user, data=FORM)
    assert response.status_code == 201
    return str(response.json()["id"])


async def set_document(session: AsyncSession, task_id: str, **values: Any) -> None:
    await session.execute(
        update(LearningDocument)
        .where(LearningDocument.task_id == uuid.UUID(task_id))
        .values(**values)
    )


@pytest.mark.parametrize("suffix", ["document", "document/status"])
async def test_both_endpoints_need_login(
    client: httpx.AsyncClient, task_id: str, suffix: str
) -> None:
    response = await call(client, "GET", f"/tasks/{task_id}/{suffix}")
    assert response.status_code == 401
    assert response.json()["error"] == "not_authenticated"


@pytest.mark.parametrize("suffix", ["document", "document/status"])
async def test_an_unknown_task_is_404(client: httpx.AsyncClient, user: User, suffix: str) -> None:
    response = await call(client, "GET", f"/tasks/{uuid.uuid4()}/{suffix}", user)
    assert response.status_code == 404
    assert response.json()["error"] == "task_not_found"


@pytest.mark.parametrize("suffix", ["document", "document/status"])
async def test_a_foreign_task_is_403(
    client: httpx.AsyncClient, other: User, task_id: str, suffix: str
) -> None:
    response = await call(client, "GET", f"/tasks/{task_id}/{suffix}", other)
    assert response.status_code == 403
    assert response.json()["error"] == "task_forbidden"


@pytest.mark.parametrize("suffix", ["document", "document/status"])
async def test_a_trashed_task_or_project_is_404(
    client: httpx.AsyncClient, user: User, project_id: str, task_id: str, suffix: str
) -> None:
    other_task = await call(client, "POST", f"/projects/{project_id}/tasks", user, data=FORM)
    trashed = str(other_task.json()["id"])
    assert (await call(client, "DELETE", f"/tasks/{trashed}", user)).status_code == 204
    response = await call(client, "GET", f"/tasks/{trashed}/{suffix}", user)
    assert (response.status_code, response.json()["error"]) == (404, "task_not_found")
    assert (await call(client, "DELETE", f"/projects/{project_id}", user)).status_code == 204
    response = await call(client, "GET", f"/tasks/{task_id}/{suffix}", user)
    assert (response.status_code, response.json()["error"]) == (404, "task_not_found")


@pytest.mark.parametrize("suffix", ["document", "document/status"])
async def test_a_bad_task_id_is_a_validation_error(
    client: httpx.AsyncClient, user: User, suffix: str
) -> None:
    response = await call(client, "GET", f"/tasks/not-a-uuid/{suffix}", user)
    assert response.status_code == 422


@pytest.mark.parametrize("suffix", ["document", "document/status"])
async def test_a_task_without_a_document_is_document_not_found(
    client: httpx.AsyncClient, session: AsyncSession, user: User, task_id: str, suffix: str
) -> None:
    await session.execute(delete(LearningDocument))
    response = await call(client, "GET", f"/tasks/{task_id}/{suffix}", user)
    assert response.status_code == 404
    assert response.json() == DOCUMENT_NOT_FOUND


async def test_status_right_after_the_upload_is_pending(
    client: httpx.AsyncClient, user: User, task_id: str
) -> None:
    response = await call(client, "GET", f"/tasks/{task_id}/document/status", user)
    assert response.status_code == 200
    assert response.json() == {
        "status": "pending",
        "generation_started_at": None,
        "generation_completed_at": None,
        "elapsed_seconds": None,
        "estimated_total_seconds": 20,
        "notice": None,
        "error": None,
    }


async def test_status_in_progress_has_server_side_elapsed_and_the_notice(
    client: httpx.AsyncClient,
    session: AsyncSession,
    user: User,
    task_id: str,
    redis_fake: MemoryRedis,
) -> None:
    started = datetime.now(UTC) - timedelta(seconds=30)
    await set_document(
        session, task_id, generation_status="in_progress", generation_started_at=started
    )
    await NoticeStore(redis_fake).set(
        uuid.UUID(task_id), "AI 서비스가 바빠 다시 시도하는 중입니다 (1/3)."
    )
    body = (await call(client, "GET", f"/tasks/{task_id}/document/status", user)).json()
    assert set(body) == STATUS_KEYS
    assert body["status"] == "in_progress"
    assert body["generation_started_at"] is not None
    assert 30 <= body["elapsed_seconds"] <= 40
    assert body["estimated_total_seconds"] == 20
    assert body["notice"] == "AI 서비스가 바빠 다시 시도하는 중입니다 (1/3)."
    assert body["error"] is None


async def test_status_survives_redis_being_down(
    app: FastAPI, client: httpx.AsyncClient, session: AsyncSession, user: User, task_id: str
) -> None:
    app.dependency_overrides[get_notice_store] = lambda: NoticeStore(DownRedis())
    await set_document(
        session, task_id, generation_status="in_progress", generation_started_at=datetime.now(UTC)
    )
    response = await call(client, "GET", f"/tasks/{task_id}/document/status", user)
    assert response.status_code == 200
    assert response.json()["notice"] is None


async def test_status_failed_shows_the_learner_message_only(
    client: httpx.AsyncClient,
    session: AsyncSession,
    user: User,
    task_id: str,
    redis_fake: MemoryRedis,
) -> None:
    now = datetime.now(UTC)
    await set_document(
        session,
        task_id,
        generation_status="failed",
        generation_started_at=now,
        generation_completed_at=now,
        generation_error="문서를 만들지 못했습니다. 다시 시도하세요.",
    )
    await NoticeStore(redis_fake).set(uuid.UUID(task_id), "낡은 안내")
    body = (await call(client, "GET", f"/tasks/{task_id}/document/status", user)).json()
    assert body["status"] == "failed"
    assert body["error"] == "문서를 만들지 못했습니다. 다시 시도하세요."
    assert body["estimated_total_seconds"] is None
    assert body["elapsed_seconds"] is None
    assert body["notice"] is None
    assert body["generation_completed_at"] is not None


async def test_a_stale_in_progress_document_is_failed_when_read(
    client: httpx.AsyncClient, session: AsyncSession, user: User, task_id: str
) -> None:
    await set_document(
        session,
        task_id,
        generation_status="in_progress",
        generation_started_at=datetime.now(UTC) - timedelta(minutes=16),
    )
    status = (await call(client, "GET", f"/tasks/{task_id}/document/status", user)).json()
    assert status["status"] == "failed"
    assert status["error"] == STALE_MESSAGE
    document = (await call(client, "GET", f"/tasks/{task_id}/document", user)).json()
    assert document["status"] == "failed"
    assert document["error"] == STALE_MESSAGE


async def test_document_is_hidden_until_completed(
    client: httpx.AsyncClient, session: AsyncSession, user: User, task_id: str
) -> None:
    for status in ("pending", "in_progress", "failed"):
        await set_document(
            session,
            task_id,
            generation_status=status,
            generation_started_at=datetime.now(UTC),
            generation_error="오류" if status == "failed" else None,
        )
        response = await call(client, "GET", f"/tasks/{task_id}/document", user)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == DOCUMENT_KEYS
        assert body["status"] == status
        assert body["content"] is None  # not the seven empty placeholder chapters
        assert body["task_id"] == task_id


async def test_completed_document_has_its_seven_chapters_and_no_internal_columns(
    client: httpx.AsyncClient, session: AsyncSession, user: User, task_id: str
) -> None:
    now = datetime.now(UTC)
    await set_document(
        session,
        task_id,
        generation_status="completed",
        generation_started_at=now,
        generation_completed_at=now,
        content=valid_doc(),
        celery_task_id="secret-job-id",
    )
    response = await call(client, "GET", f"/tasks/{task_id}/document", user)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == DOCUMENT_KEYS
    assert body["status"] == "completed"
    assert body["content"] == valid_doc()
    assert body["error"] is None
    assert body["generation_completed_at"] is not None
    assert "secret-job-id" not in response.text
    for leaked in ("celery_task_id", "storage_path", "id", "generation_status"):
        assert leaked not in body
    status = (await call(client, "GET", f"/tasks/{task_id}/document/status", user)).json()
    assert status["status"] == "completed"
    assert status["estimated_total_seconds"] is None
    assert "secret-job-id" not in str(status)


async def test_the_notice_store_dependency_is_closed_after_the_request() -> None:
    from src.api import dependencies

    generator = dependencies.get_notice_store()
    store = await anext(generator)
    assert isinstance(store, NoticeStore)
    with pytest.raises(StopAsyncIteration):
        await anext(generator)
