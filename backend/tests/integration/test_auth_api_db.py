import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from datetime import timedelta
from http.cookies import Morsel, SimpleCookie
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.api.dependencies import ACCESS_TOKEN_COOKIE, REFRESH_COOKIE_PATH, REFRESH_TOKEN_COOKIE
from src.config import AppSettings
from src.db import session as session_module
from src.db.session import create_engine, create_session_factory, get_session
from src.main import create_app
from src.models import RefreshToken, User
from src.utils.jwt import JWTSettings, create_access_token, create_refresh_token, get_jwt_settings
from src.utils.security import hash_refresh_token

SETTINGS = JWTSettings(  # type: ignore[call-arg]
    _env_file=None, secret_key="a" * 40, refresh_secret_key="r" * 40
)
EMAIL = "student@example.com"
PASSWORD = "Passw0rdOK"
CREDENTIALS = {"email": EMAIL, "password": PASSWORD}
BASE = "/api/v1/auth"
NOT_AUTHENTICATED = {"error": "not_authenticated", "message": "로그인이 필요합니다."}
SESSION_EXPIRED = {
    "error": "session_expired",
    "message": "세션이 만료되었습니다. 다시 로그인하세요.",
}
INVALID_CREDENTIALS = {
    "error": "invalid_credentials",
    "message": "이메일 또는 비밀번호가 올바르지 않습니다.",
}

ASGIApp = Callable[..., Awaitable[None]]


def build_app(session: AsyncSession | None = None, environment: str = "development") -> FastAPI:
    app = create_app(AppSettings(_env_file=None, environment=environment))  # type: ignore[call-arg]
    if session is not None:

        async def use_test_session() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_session] = use_test_session
    app.dependency_overrides[get_jwt_settings] = lambda: SETTINGS
    return app


def http_client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async with http_client(build_app(session)) as c:
        yield c


@pytest.fixture
async def production_client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async with http_client(build_app(session, "production")) as c:
        yield c


def set_cookies(response: httpx.Response) -> dict[str, Morsel[str]]:
    """The Set-Cookie headers of a response, by cookie name (the last one wins)."""
    jar: dict[str, Morsel[str]] = {}
    for header in response.headers.get_list("set-cookie"):
        parsed: SimpleCookie = SimpleCookie()
        parsed.load(header)
        jar.update(parsed)
    return jar


def assert_cleared(response: httpx.Response) -> None:
    cookies = set_cookies(response)
    assert set(cookies) == {ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE}
    assert len(response.headers.get_list("set-cookie")) == 2
    assert cookies[ACCESS_TOKEN_COOKIE].value == ""
    assert cookies[ACCESS_TOKEN_COOKIE]["path"] == "/"
    assert cookies[REFRESH_TOKEN_COOKIE].value == ""
    assert cookies[REFRESH_TOKEN_COOKIE]["path"] == REFRESH_COOKIE_PATH
    for morsel in cookies.values():
        assert morsel["max-age"] == "0"
        assert morsel["httponly"]
        assert morsel["samesite"].lower() == "strict"


async def send(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    access: str | None = None,
    refresh: str | None = None,
    json: Any = None,
) -> httpx.Response:
    """A request carrying exactly the given cookies (the client's cookie jar is not used)."""
    client.cookies.clear()
    if access is not None:
        client.cookies.set(ACCESS_TOKEN_COOKIE, access, path="/")
    if refresh is not None:
        client.cookies.set(REFRESH_TOKEN_COOKIE, refresh, path=REFRESH_COOKIE_PATH)
    return await client.request(method, f"{BASE}{path}", json=json)


async def register(client: httpx.AsyncClient, email: str = EMAIL) -> httpx.Response:
    return await send(client, "POST", "/register", json={"email": email, "password": PASSWORD})


async def login(client: httpx.AsyncClient, email: str = EMAIL) -> httpx.Response:
    return await send(client, "POST", "/login", json={"email": email, "password": PASSWORD})


async def logged_in(client: httpx.AsyncClient, email: str = EMAIL) -> tuple[str, str]:
    """Register and log in; returns (access token, refresh token)."""
    assert (await register(client, email)).status_code == 201
    cookies = set_cookies(await login(client, email))
    return cookies[ACCESS_TOKEN_COOKIE].value, cookies[REFRESH_TOKEN_COOKIE].value


async def user_row(session: AsyncSession, email: str = EMAIL) -> User:
    return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def token_row(session: AsyncSession, token: str) -> RefreshToken | None:
    return (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
        )
    ).scalar_one_or_none()


async def token_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(RefreshToken))).scalar_one()


# --- register -----------------------------------------------------------------------------


async def test_register_creates_the_account(client: httpx.AsyncClient) -> None:
    response = await register(client)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "skill_level"}
    assert uuid.UUID(body["id"])
    assert body["email"] == EMAIL
    assert body["skill_level"] == "Complete Beginner"


async def test_register_does_not_log_in(client: httpx.AsyncClient) -> None:
    response = await register(client)
    assert response.headers.get_list("set-cookie") == []
    assert "token" not in response.text


async def test_register_stores_a_hash_not_the_password(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    response = await register(client)

    assert "password" not in response.text
    stored = await user_row(session)
    assert stored.password_hash != PASSWORD
    assert stored.password_hash.startswith("$2")
    assert str(stored.id) == response.json()["id"]


async def test_register_normalizes_the_email(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    response = await register(client, "  Student@Example.COM ")
    assert response.status_code == 201
    assert response.json()["email"] == EMAIL
    assert (await user_row(session)).email == EMAIL


@pytest.mark.parametrize("second", [EMAIL, "STUDENT@example.com"])
async def test_register_refuses_a_duplicate_email_in_any_case(
    client: httpx.AsyncClient, second: str
) -> None:
    await register(client)

    response = await register(client, second)

    assert response.status_code == 409
    assert response.json()["error"] == "email_already_registered"


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "", "x" * 300 + "@example.com"])
async def test_register_refuses_an_invalid_email(client: httpx.AsyncClient, email: str) -> None:
    response = await register(client, email)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_email"


@pytest.mark.parametrize("password", ["short1", "allletters", "12345678", ""])
async def test_register_refuses_a_weak_password(client: httpx.AsyncClient, password: str) -> None:
    response = await send(client, "POST", "/register", json={"email": EMAIL, "password": password})
    assert response.status_code == 422
    assert response.json()["error"] == "weak_password"


@pytest.mark.parametrize(
    "body", [{}, {"email": EMAIL}, {"password": PASSWORD}, {"email": 1, "password": PASSWORD}]
)
async def test_register_with_missing_or_mistyped_fields_is_a_validation_error(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    response = await send(client, "POST", "/register", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_a_failed_register_creates_nothing(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await register(client, "not-an-email")
    assert (await session.execute(select(func.count()).select_from(User))).scalar_one() == 0


# --- login --------------------------------------------------------------------------------


async def test_login_returns_the_user_and_sets_the_two_cookies(
    client: httpx.AsyncClient,
) -> None:
    created = (await register(client)).json()

    response = await login(client)

    assert response.status_code == 200
    assert response.json() == created
    cookies = set_cookies(response)
    assert set(cookies) == {ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE}
    assert len(response.headers.get_list("set-cookie")) == 2
    assert "token" not in response.text


async def test_login_cookie_attributes(client: httpx.AsyncClient) -> None:
    await register(client)

    cookies = set_cookies(await login(client))

    access, refresh = cookies[ACCESS_TOKEN_COOKIE], cookies[REFRESH_TOKEN_COOKIE]
    assert access["path"] == "/"
    assert refresh["path"] == "/api/v1/auth" == REFRESH_COOKIE_PATH
    for morsel in (access, refresh):
        assert morsel["httponly"]
        assert morsel["samesite"].lower() == "strict"
        assert not morsel["secure"]
        assert morsel.value
    assert 890 <= int(access["max-age"]) <= 900
    assert 7 * 86400 - 10 <= int(refresh["max-age"]) <= 7 * 86400


async def test_login_cookies_are_secure_only_in_production(
    production_client: httpx.AsyncClient,
) -> None:
    await register(production_client)

    login_cookies = set_cookies(await login(production_client))
    assert all(morsel["secure"] for morsel in login_cookies.values())

    cleared = await send(production_client, "POST", "/logout")
    assert all(morsel["secure"] for morsel in set_cookies(cleared).values())


async def test_login_cookies_authenticate_later_requests(client: httpx.AsyncClient) -> None:
    await register(client)
    await login(client)

    # The client's own cookie jar replays the cookies exactly as a browser would.
    response = await client.get(f"{BASE}/me")

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


async def test_login_records_the_login_and_a_hashed_refresh_token(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await register(client)
    assert (await user_row(session)).last_login_at is None

    cookies = set_cookies(await login(client))

    stored_user = await user_row(session)
    assert stored_user.last_login_at is not None
    refresh = cookies[REFRESH_TOKEN_COOKIE].value
    row = await token_row(session, refresh)
    assert row is not None
    assert row.user_id == stored_user.id
    assert not row.revoked
    assert row.token_hash != refresh
    assert await token_count(session) == 1


async def test_login_failures_are_identical_and_set_no_cookie(client: httpx.AsyncClient) -> None:
    await register(client)

    wrong_password = await send(
        client, "POST", "/login", json={"email": EMAIL, "password": "Wrong1234"}
    )
    unknown_email = await send(
        client, "POST", "/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    bad_email = await send(client, "POST", "/login", json={"email": "x", "password": PASSWORD})

    for response in (wrong_password, unknown_email, bad_email):
        assert response.status_code == 401
        assert response.json() == INVALID_CREDENTIALS
        assert response.headers.get_list("set-cookie") == []


async def test_a_failed_login_stores_no_refresh_token(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await register(client)
    await send(client, "POST", "/login", json={"email": EMAIL, "password": "Wrong1234"})
    assert await token_count(session) == 0


@pytest.mark.parametrize("body", [{}, {"email": EMAIL}, {"password": PASSWORD}])
async def test_login_with_missing_fields_is_a_validation_error(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    response = await send(client, "POST", "/login", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_each_login_gets_its_own_refresh_token(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await register(client)
    first = set_cookies(await login(client))[REFRESH_TOKEN_COOKIE].value
    second = set_cookies(await login(client))[REFRESH_TOKEN_COOKIE].value

    assert first != second
    assert await token_count(session) == 2


# --- me -----------------------------------------------------------------------------------


async def test_me_returns_the_current_user(client: httpx.AsyncClient) -> None:
    await logged_in(client, "other@example.com")  # a different user exists too
    created = (await register(client)).json()
    access = set_cookies(await login(client))[ACCESS_TOKEN_COOKIE].value

    response = await send(client, "GET", "/me", access=access)

    assert response.status_code == 200
    assert response.json() == created
    assert set(response.json()) == {"id", "email", "skill_level"}


async def test_me_without_a_cookie_is_not_authenticated(client: httpx.AsyncClient) -> None:
    response = await send(client, "GET", "/me")
    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_me_with_an_expired_token_is_session_expired(
    client: httpx.AsyncClient,
) -> None:
    user_id = (await register(client)).json()["id"]
    expired = create_access_token(user_id, settings=SETTINGS, expires_delta=timedelta(seconds=-1))

    response = await send(client, "GET", "/me", access=expired)

    assert response.status_code == 401
    assert response.json() == SESSION_EXPIRED


async def test_me_with_garbage_is_not_authenticated(client: httpx.AsyncClient) -> None:
    response = await send(client, "GET", "/me", access="garbage")
    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


# --- logout -------------------------------------------------------------------------------


async def test_logout_revokes_only_this_devices_token(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    access, refresh = await logged_in(client)
    other_device = set_cookies(await login(client))[REFRESH_TOKEN_COOKIE].value

    response = await send(client, "POST", "/logout", access=access, refresh=refresh)

    assert response.status_code == 204
    assert response.content == b""
    assert_cleared(response)
    revoked = await token_row(session, refresh)
    assert revoked is not None and revoked.revoked and revoked.revoked_at is not None
    untouched = await token_row(session, other_device)
    assert untouched is not None and not untouched.revoked


async def test_logout_works_with_an_expired_access_cookie(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, refresh = await logged_in(client)
    user_id = str((await user_row(session)).id)
    expired = create_access_token(user_id, settings=SETTINGS, expires_delta=timedelta(seconds=-1))

    response = await send(client, "POST", "/logout", access=expired, refresh=refresh)

    assert response.status_code == 204
    assert_cleared(response)
    row = await token_row(session, refresh)
    assert row is not None and row.revoked


@pytest.mark.parametrize("refresh", [None, "garbage", "", "a.b.c"])
async def test_logout_without_a_usable_cookie_still_succeeds(
    client: httpx.AsyncClient, refresh: str | None
) -> None:
    response = await send(client, "POST", "/logout", refresh=refresh)
    assert response.status_code == 204
    assert_cleared(response)


async def test_logout_with_an_unknown_but_valid_looking_token_succeeds(
    client: httpx.AsyncClient,
) -> None:
    unknown = create_refresh_token(str(uuid.uuid4()), settings=SETTINGS)
    response = await send(client, "POST", "/logout", refresh=unknown)
    assert response.status_code == 204
    assert_cleared(response)


async def test_logout_twice_is_idempotent(client: httpx.AsyncClient) -> None:
    _, refresh = await logged_in(client)

    first = await send(client, "POST", "/logout", refresh=refresh)
    second = await send(client, "POST", "/logout", refresh=refresh)

    assert first.status_code == second.status_code == 204
    assert_cleared(second)


async def test_a_logged_out_session_cannot_be_refreshed(client: httpx.AsyncClient) -> None:
    _, refresh = await logged_in(client)
    await send(client, "POST", "/logout", refresh=refresh)

    response = await send(client, "POST", "/refresh", refresh=refresh)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


# --- refresh ------------------------------------------------------------------------------


async def test_refresh_rotates_the_token_and_the_cookies(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    access, refresh = await logged_in(client)

    response = await send(client, "POST", "/refresh", refresh=refresh)

    assert response.status_code == 204
    assert response.content == b""
    cookies = set_cookies(response)
    assert set(cookies) == {ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE}
    new_access = cookies[ACCESS_TOKEN_COOKIE].value
    new_refresh = cookies[REFRESH_TOKEN_COOKIE].value
    assert new_access != access and new_refresh != refresh
    assert cookies[ACCESS_TOKEN_COOKIE]["path"] == "/"
    assert cookies[REFRESH_TOKEN_COOKIE]["path"] == REFRESH_COOKIE_PATH
    assert 890 <= int(cookies[ACCESS_TOKEN_COOKIE]["max-age"]) <= 900
    assert 7 * 86400 - 10 <= int(cookies[REFRESH_TOKEN_COOKIE]["max-age"]) <= 7 * 86400
    for morsel in cookies.values():
        assert morsel["httponly"] and morsel["samesite"].lower() == "strict"

    old_row = await token_row(session, refresh)
    new_row = await token_row(session, new_refresh)
    assert old_row is not None and old_row.revoked
    assert new_row is not None and not new_row.revoked
    me = await send(client, "GET", "/me", access=new_access)
    assert me.status_code == 200


async def test_an_old_refresh_token_cannot_be_reused(client: httpx.AsyncClient) -> None:
    _, refresh = await logged_in(client)
    await send(client, "POST", "/refresh", refresh=refresh)

    reuse = await send(client, "POST", "/refresh", refresh=refresh)

    assert reuse.status_code == 401
    assert reuse.json() == NOT_AUTHENTICATED
    assert_cleared(reuse)


async def test_refresh_without_a_cookie_clears_the_cookies(client: httpx.AsyncClient) -> None:
    response = await send(client, "POST", "/refresh", access="stale-access")
    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED
    assert_cleared(response)


async def test_refresh_with_garbage_clears_the_cookies(client: httpx.AsyncClient) -> None:
    response = await send(client, "POST", "/refresh", refresh="garbage")
    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED
    assert_cleared(response)


async def test_refresh_with_an_access_token_in_its_place_is_refused(
    client: httpx.AsyncClient,
) -> None:
    access, _ = await logged_in(client)
    response = await send(client, "POST", "/refresh", refresh=access)
    assert response.status_code == 401
    assert_cleared(response)


async def test_refresh_with_an_unknown_token_clears_the_cookies(
    client: httpx.AsyncClient,
) -> None:
    unknown = create_refresh_token(str(uuid.uuid4()), settings=SETTINGS)
    response = await send(client, "POST", "/refresh", refresh=unknown)
    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED
    assert_cleared(response)


async def test_an_expired_refresh_token_means_session_expired(
    client: httpx.AsyncClient,
) -> None:
    user_id = (await register(client)).json()["id"]
    expired = create_refresh_token(user_id, settings=SETTINGS, expires_delta=timedelta(seconds=-1))

    response = await send(client, "POST", "/refresh", refresh=expired)

    assert response.status_code == 401
    assert response.json() == SESSION_EXPIRED
    assert_cleared(response)


async def test_a_failed_refresh_changes_nothing_in_the_database(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, refresh = await logged_in(client)
    await send(client, "POST", "/logout", refresh=refresh)
    before = await token_count(session)

    await send(client, "POST", "/refresh", refresh=refresh)

    assert await token_count(session) == before


# --- full flow ----------------------------------------------------------------------------


async def test_full_session_lifecycle_with_the_cookie_jar(client: httpx.AsyncClient) -> None:
    assert (await client.post(f"{BASE}/register", json=CREDENTIALS)).status_code == 201
    assert (await client.get(f"{BASE}/me")).status_code == 401

    assert (await client.post(f"{BASE}/login", json=CREDENTIALS)).status_code == 200
    me = await client.get(f"{BASE}/me")
    assert me.status_code == 200 and me.json()["email"] == EMAIL

    assert (await client.post(f"{BASE}/refresh")).status_code == 204
    assert (await client.get(f"{BASE}/me")).status_code == 200

    assert (await client.post(f"{BASE}/logout")).status_code == 204
    assert (await client.get(f"{BASE}/me")).status_code == 401
    refresh_after_logout = await client.post(f"{BASE}/refresh")
    assert refresh_after_logout.status_code == 401
    assert_cleared(refresh_after_logout)


async def test_openapi_lists_the_five_operations(client: httpx.AsyncClient) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]
    operations = {
        (method.upper(), path)
        for path, item in paths.items()
        if path.startswith(BASE)
        for method in item
    }
    assert operations == {
        ("POST", f"{BASE}/register"),
        ("POST", f"{BASE}/login"),
        ("GET", f"{BASE}/me"),
        ("POST", f"{BASE}/logout"),
        ("POST", f"{BASE}/refresh"),
    }


# --- really committed (real get_session, a different session reads the result) -------------


@pytest.fixture
async def committed_factory(
    test_database_url: str, migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """The app's real get_session, pointed at the test database, with cleanup afterwards."""
    engine = create_engine(test_database_url)
    factory = create_session_factory(engine)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: factory)
    yield factory
    async with factory() as cleanup:
        await cleanup.execute(delete(User))  # refresh tokens go with it (ON DELETE CASCADE)
        await cleanup.commit()
    await engine.dispose()


@pytest.fixture
async def committed_client(
    committed_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[httpx.AsyncClient]:
    async with http_client(build_app()) as c:
        yield c


async def test_register_is_committed(
    committed_client: httpx.AsyncClient, committed_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await register(committed_client)
    assert response.status_code == 201

    async with committed_factory() as other:
        stored = await user_row(other)
    assert str(stored.id) == response.json()["id"]
    assert stored.password_hash.startswith("$2")


async def test_login_is_committed(
    committed_client: httpx.AsyncClient, committed_factory: async_sessionmaker[AsyncSession]
) -> None:
    await register(committed_client)
    refresh = set_cookies(await login(committed_client))[REFRESH_TOKEN_COOKIE].value

    async with committed_factory() as other:
        assert (await user_row(other)).last_login_at is not None
        row = await token_row(other, refresh)
    assert row is not None and not row.revoked


async def test_logout_is_committed(
    committed_client: httpx.AsyncClient, committed_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, refresh = await logged_in(committed_client)
    await send(committed_client, "POST", "/logout", refresh=refresh)

    async with committed_factory() as other:
        row = await token_row(other, refresh)
    assert row is not None and row.revoked


async def test_refresh_is_committed(
    committed_client: httpx.AsyncClient, committed_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, refresh = await logged_in(committed_client)
    response = await send(committed_client, "POST", "/refresh", refresh=refresh)
    new_refresh = set_cookies(response)[REFRESH_TOKEN_COOKIE].value

    async with committed_factory() as other:
        old_row = await token_row(other, refresh)
        new_row = await token_row(other, new_refresh)
    assert old_row is not None and old_row.revoked
    assert new_row is not None and not new_row.revoked


async def test_the_data_is_committed_before_the_response_is_sent(
    committed_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A client that gets its 201 must already be able to log in: commit happens first."""
    app = build_app()
    visible_when_response_starts: list[bool] = []

    async def recording_app(
        scope: MutableMapping[str, Any], receive: Any, send_message: Any
    ) -> None:
        async def spying_send(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start" and scope["path"].endswith("/register"):
                async with committed_factory() as other:
                    count = (
                        await other.execute(select(func.count()).select_from(User))
                    ).scalar_one()
                visible_when_response_starts.append(count == 1)
            await send_message(message)

        await app(scope, receive, spying_send)

    async with http_client(recording_app) as spying_client:
        assert (await register(spying_client)).status_code == 201

    assert visible_when_response_starts == [True]
