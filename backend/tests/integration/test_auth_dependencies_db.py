import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies import ACCESS_TOKEN_COOKIE, CurrentUser, CurrentUserId
from src.config import AppSettings
from src.db.session import get_session
from src.main import create_app
from src.models import User
from src.utils.jwt import JWTSettings, create_access_token, create_refresh_token, get_jwt_settings

SETTINGS = JWTSettings(  # type: ignore[call-arg]
    _env_file=None, secret_key="a" * 40, refresh_secret_key="r" * 40
)
OTHER_SETTINGS = JWTSettings(  # type: ignore[call-arg]
    _env_file=None, secret_key="z" * 40, refresh_secret_key="y" * 40
)
NOT_AUTHENTICATED = {"error": "not_authenticated", "message": "로그인이 필요합니다."}
SESSION_EXPIRED = {
    "error": "session_expired",
    "message": "세션이 만료되었습니다. 다시 로그인하세요.",
}


def build_app(session: AsyncSession) -> FastAPI:
    app = create_app(AppSettings(_env_file=None))  # type: ignore[call-arg]

    async def use_test_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = use_test_session
    app.dependency_overrides[get_jwt_settings] = lambda: SETTINGS

    @app.get("/t/me")
    async def me(user: CurrentUser) -> dict[str, str]:
        return {"id": str(user.id), "email": user.email}

    @app.get("/t/user-id")
    async def user_id(current_user_id: CurrentUserId) -> dict[str, str]:
        return {"id": str(current_user_id)}

    return app


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=build_app(session))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def saved_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


async def get_as(client: httpx.AsyncClient, path: str, token: str | None = None) -> httpx.Response:
    """GET with the access cookie set to `token` (or no cookie at all when it is None)."""
    client.cookies.clear()
    if token is not None:
        client.cookies.set(ACCESS_TOKEN_COOKIE, token)
    return await client.get(path)


async def test_a_valid_access_cookie_gives_the_current_user(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await saved_user(session)
    token = create_access_token(str(user.id), settings=SETTINGS)

    response = await get_as(client, "/t/me", token)

    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "email": "student@example.com"}


async def test_each_request_gets_its_own_user(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    alice = await saved_user(session, "alice@example.com")
    bob = await saved_user(session, "bob@example.com")

    for user in (alice, bob):
        token = create_access_token(str(user.id), settings=SETTINGS)
        response = await get_as(client, "/t/me", token)
        assert response.json()["email"] == user.email


async def test_no_cookie_means_not_authenticated(client: httpx.AsyncClient) -> None:
    response = await client.get("/t/me")
    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_an_empty_cookie_means_not_authenticated(client: httpx.AsyncClient) -> None:
    response = await get_as(client, "/t/me", "")
    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_an_expired_token_means_the_session_expired(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await saved_user(session)
    token = create_access_token(
        str(user.id), settings=SETTINGS, expires_delta=timedelta(seconds=-1)
    )

    response = await get_as(client, "/t/me", token)

    assert response.status_code == 401
    assert response.json() == SESSION_EXPIRED


@pytest.mark.parametrize("garbage", ["garbage", "a.b.c"])
async def test_garbage_in_the_cookie_is_rejected(client: httpx.AsyncClient, garbage: str) -> None:
    response = await get_as(client, "/t/me", garbage)
    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_a_refresh_token_is_not_accepted_as_an_access_token(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await saved_user(session)
    refresh = create_refresh_token(str(user.id), settings=SETTINGS)

    response = await get_as(client, "/t/me", refresh)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_a_token_signed_with_another_secret_is_rejected(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await saved_user(session)
    forged = create_access_token(str(user.id), settings=OTHER_SETTINGS)

    response = await get_as(client, "/t/me", forged)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_a_token_for_a_user_that_no_longer_exists_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    token = create_access_token(str(uuid.uuid4()), settings=SETTINGS)

    response = await get_as(client, "/t/me", token)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_a_deleted_user_loses_access_immediately(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await saved_user(session)
    token = create_access_token(str(user.id), settings=SETTINGS)
    assert (await get_as(client, "/t/me", token)).status_code == 200

    await session.delete(user)
    await session.flush()

    assert (await get_as(client, "/t/me", token)).status_code == 401


async def test_a_subject_that_is_not_a_user_id_is_rejected(client: httpx.AsyncClient) -> None:
    token = create_access_token("123", settings=SETTINGS)

    response = await get_as(client, "/t/me", token)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_a_bearer_header_is_not_accepted_only_the_cookie_is(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await saved_user(session)
    token = create_access_token(str(user.id), settings=SETTINGS)

    response = await client.get("/t/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_the_user_id_dependency_needs_no_database_lookup(
    client: httpx.AsyncClient,
) -> None:
    """CurrentUserId only checks the token, so it works even for an id with no row."""
    some_id = uuid.uuid4()
    token = create_access_token(str(some_id), settings=SETTINGS)

    response = await get_as(client, "/t/user-id", token)

    assert response.status_code == 200
    assert response.json() == {"id": str(some_id)}


async def test_the_user_id_dependency_rejects_the_same_bad_tokens(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.get("/t/user-id")).json() == NOT_AUTHENTICATED
    expired = create_access_token(
        str(uuid.uuid4()), settings=SETTINGS, expires_delta=timedelta(seconds=-1)
    )
    response = await get_as(client, "/t/user-id", expired)
    assert response.json() == SESSION_EXPIRED


async def test_unprotected_routes_still_work_without_a_cookie(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_rejections_carry_the_request_id_header(client: httpx.AsyncClient) -> None:
    response = await client.get("/t/me", headers={"X-Request-ID": "trace-protected"})
    assert response.status_code == 401
    assert response.headers["x-request-id"] == "trace-protected"
