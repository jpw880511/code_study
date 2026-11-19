import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import Engine, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.api.dependencies import ACCESS_TOKEN_COOKIE
from src.config import AppSettings
from src.db import session as session_module
from src.db.session import create_engine, create_session_factory, get_session
from src.main import create_app
from src.models import Project, User
from src.utils.jwt import JWTSettings, create_access_token, create_refresh_token, get_jwt_settings

SETTINGS = JWTSettings(  # type: ignore[call-arg]
    _env_file=None, secret_key="a" * 40, refresh_secret_key="r" * 40
)
BASE = "/api/v1/projects"
RESPONSE_KEYS = {"id", "title", "description", "created_at", "updated_at", "last_activity_at"}
NOT_AUTHENTICATED = {"error": "not_authenticated", "message": "로그인이 필요합니다."}
SESSION_EXPIRED = {
    "error": "session_expired",
    "message": "세션이 만료되었습니다. 다시 로그인하세요.",
}
NOT_FOUND = {
    "error": "project_not_found",
    "message": "요청한 프로젝트를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 프로젝트입니다.",
}
FORBIDDEN = {"error": "project_forbidden", "message": "이 프로젝트에 접근할 권한이 없습니다."}
TITLE_TOO_SHORT = {
    "error": "invalid_project_title",
    "message": "프로젝트 제목은 최소 1자 이상이어야 합니다.",
}
TITLE_TOO_LONG = {
    "error": "invalid_project_title",
    "message": "프로젝트 제목은 최대 255자까지 입력 가능합니다.",
}
DESCRIPTION_TOO_LONG = {
    "error": "invalid_project_description",
    "message": "프로젝트 설명은 최대 2000자까지 입력 가능합니다.",
}
OLD = datetime(2020, 1, 1, tzinfo=UTC)


def build_app(session: AsyncSession | None = None) -> FastAPI:
    app = create_app(AppSettings(_env_file=None))  # type: ignore[call-arg]
    if session is not None:

        async def use_test_session() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_session] = use_test_session
    app.dependency_overrides[get_jwt_settings] = lambda: SETTINGS
    return app


def http_client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def token_for(user: User, **options: Any) -> str:
    return create_access_token(str(user.id), settings=SETTINGS, **options)


async def call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    user: User | None = None,
    *,
    json: Any = None,
    access: str | None = None,
) -> httpx.Response:
    """A request carrying exactly one access cookie (the client's cookie jar is not used)."""
    client.cookies.clear()
    cookie = access if access is not None else (token_for(user) if user else None)
    if cookie is not None:
        client.cookies.set(ACCESS_TOKEN_COOKIE, cookie, path="/")
    return await client.request(method, f"{BASE}{path}", json=json)


async def create_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async with http_client(build_app(session)) as c:
        yield c


@pytest.fixture
async def user(session: AsyncSession) -> User:
    return await create_user(session)


@pytest.fixture
async def other(session: AsyncSession) -> User:
    return await create_user(session, "other@example.com")


async def make_project(
    client: httpx.AsyncClient, user: User, title: str = "프로젝트", **body: Any
) -> dict[str, Any]:
    response = await call(client, "POST", "", user, json={"title": title, **body})
    assert response.status_code == 201
    created: dict[str, Any] = response.json()
    return created


def assert_project_shape(body: dict[str, Any]) -> None:
    assert set(body) == RESPONSE_KEYS
    uuid.UUID(body["id"])
    assert isinstance(body["title"], str)
    assert body["description"] is None or isinstance(body["description"], str)
    for key in ("created_at", "updated_at", "last_activity_at"):
        parsed = datetime.fromisoformat(body[key])
        assert parsed.utcoffset() == timedelta(0), key


# --- authentication (every operation) ------------------------------------------------------

OPERATIONS = [
    ("GET", "", None),
    ("POST", "", {"title": "x"}),
    ("GET", "/{id}", None),
    ("PATCH", "/{id}", {"title": "x"}),
    ("DELETE", "/{id}", None),
]


@pytest.mark.parametrize(("method", "path", "body"), OPERATIONS)
async def test_every_operation_needs_the_access_cookie(
    client: httpx.AsyncClient, method: str, path: str, body: Any
) -> None:
    response = await call(client, method, path.format(id=uuid.uuid4()), json=body)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


@pytest.mark.parametrize(("method", "path", "body"), OPERATIONS)
async def test_an_expired_session_is_reported_as_such(
    client: httpx.AsyncClient, user: User, method: str, path: str, body: Any
) -> None:
    expired = token_for(user, expires_delta=timedelta(seconds=-1))

    response = await call(client, method, path.format(id=uuid.uuid4()), json=body, access=expired)

    assert response.status_code == 401
    assert response.json() == SESSION_EXPIRED


@pytest.mark.parametrize(("method", "path", "body"), OPERATIONS)
async def test_a_refresh_token_or_garbage_is_not_an_access_token(
    client: httpx.AsyncClient, user: User, method: str, path: str, body: Any
) -> None:
    refresh = create_refresh_token(str(user.id), settings=SETTINGS)
    for bad in (refresh, "garbage"):
        response = await call(client, method, path.format(id=uuid.uuid4()), json=body, access=bad)
        assert response.status_code == 401
        assert response.json()["error"] == "not_authenticated"


async def test_a_token_for_a_deleted_user_is_refused(client: httpx.AsyncClient) -> None:
    ghost = User(id=uuid.uuid4(), email="ghost@example.com", password_hash="x")

    response = await call(client, "GET", "", ghost)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


async def test_unauthenticated_requests_do_not_validate_the_body_first_or_touch_data(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    response = await call(client, "POST", "", json={"title": "x"})

    assert response.status_code == 401
    assert (await session.execute(select(Project))).first() is None


# --- POST /projects ------------------------------------------------------------------------


async def test_create_returns_201_with_the_contract_shape(
    client: httpx.AsyncClient, user: User
) -> None:
    response = await call(
        client, "POST", "", user, json={"title": "  첫 프로젝트 ", "description": " 설명 "}
    )

    assert response.status_code == 201
    body = response.json()
    assert_project_shape(body)
    assert body["title"] == "첫 프로젝트"
    assert body["description"] == "설명"
    assert body["last_activity_at"] == body["created_at"]


async def test_create_without_a_description_returns_null(
    client: httpx.AsyncClient, user: User
) -> None:
    for payload in (
        {"title": "A"},
        {"title": "B", "description": None},
        {"title": "C", "description": " "},
    ):
        response = await call(client, "POST", "", user, json=payload)
        assert response.status_code == 201
        assert response.json()["description"] is None


async def test_create_never_exposes_internal_columns(client: httpx.AsyncClient, user: User) -> None:
    body = await make_project(client, user)

    for forbidden in ("user_id", "deletion_status", "trashed_at", "scheduled_deletion_at"):
        assert forbidden not in body


async def test_create_ignores_client_supplied_internal_fields(
    client: httpx.AsyncClient, user: User, other: User, session: AsyncSession
) -> None:
    response = await call(
        client,
        "POST",
        "",
        user,
        json={
            "title": "해킹",
            "id": str(uuid.uuid4()),
            "user_id": str(other.id),
            "deletion_status": "trashed",
            "created_at": "1999-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 201
    row = (await session.execute(select(Project))).scalar_one()
    assert row.user_id == user.id
    assert row.deletion_status == "active"
    assert str(row.id) == response.json()["id"]
    assert row.created_at.year >= 2026


async def test_create_with_a_blank_title_is_422(client: httpx.AsyncClient, user: User) -> None:
    for title in ("", "   "):
        response = await call(client, "POST", "", user, json={"title": title})
        assert response.status_code == 422
        assert response.json() == TITLE_TOO_SHORT


async def test_create_with_a_too_long_title_or_description_is_422(
    client: httpx.AsyncClient, user: User
) -> None:
    response = await call(client, "POST", "", user, json={"title": "a" * 256})
    assert (response.status_code, response.json()) == (422, TITLE_TOO_LONG)

    response = await call(client, "POST", "", user, json={"title": "ok", "description": "a" * 2001})
    assert (response.status_code, response.json()) == (422, DESCRIPTION_TOO_LONG)


async def test_create_accepts_the_maximum_lengths(client: httpx.AsyncClient, user: User) -> None:
    response = await call(
        client, "POST", "", user, json={"title": "가" * 255, "description": "나" * 2000}
    )

    assert response.status_code == 201
    assert len(response.json()["title"]) == 255


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"description": "설명만"},
        {"title": None},
        {"title": 123},
        {"title": ["a"]},
        {"title": "ok", "description": 5},
    ],
)
async def test_create_with_a_missing_or_mistyped_field_is_a_validation_error(
    client: httpx.AsyncClient, user: User, payload: dict[str, Any]
) -> None:
    response = await call(client, "POST", "", user, json=payload)

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_create_with_a_malformed_body_is_a_validation_error(
    client: httpx.AsyncClient, user: User
) -> None:
    client.cookies.clear()
    client.cookies.set(ACCESS_TOKEN_COOKIE, token_for(user), path="/")

    for content in (b"not json", b"[]", b'"text"'):
        response = await client.post(
            BASE, content=content, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
        assert response.json()["error"] == "validation_error"


async def test_create_stores_markup_and_quotes_literally(
    client: httpx.AsyncClient, user: User
) -> None:
    title = "<img src=x onerror=alert(1)> ' OR 1=1 --"

    created = await make_project(client, user, title)
    fetched = await call(client, "GET", f"/{created['id']}", user)

    assert fetched.json()["title"] == title


async def test_create_with_a_nul_character_is_422_not_a_server_error(
    client: httpx.AsyncClient, user: User
) -> None:
    response = await call(client, "POST", "", user, json={"title": "a\u0000b"})

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_project_title"


# --- GET /projects -------------------------------------------------------------------------


async def test_list_is_an_empty_array_without_projects(
    client: httpx.AsyncClient, user: User
) -> None:
    response = await call(client, "GET", "", user)

    assert response.status_code == 200
    assert response.json() == []


async def test_list_returns_the_contract_shape_for_each_project(
    client: httpx.AsyncClient, user: User
) -> None:
    await make_project(client, user, "A")
    await make_project(client, user, "B", description="설명")

    response = await call(client, "GET", "", user)

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    for item in items:
        assert_project_shape(item)


async def test_list_is_ordered_by_last_activity_then_creation_newest_first(
    client: httpx.AsyncClient, user: User, session: AsyncSession
) -> None:
    ids = {}
    for title in ("a", "b", "c", "d"):
        ids[title] = (await make_project(client, user, title))["id"]
    day = timedelta(days=1)
    plan = {
        "a": (OLD + 3 * day, OLD),
        "b": (OLD + 5 * day, OLD),
        "c": (OLD + day, OLD + day),
        "d": (OLD + day, OLD + 2 * day),
    }
    for title, (activity, created) in plan.items():
        await session.execute(
            update(Project)
            .where(Project.id == uuid.UUID(ids[title]))
            .values(last_activity_at=activity, created_at=created)
        )

    response = await call(client, "GET", "", user)

    assert [p["title"] for p in response.json()] == ["b", "a", "d", "c"]


async def test_list_shows_only_the_callers_projects(
    client: httpx.AsyncClient, user: User, other: User
) -> None:
    mine = await make_project(client, user, "내 것")
    theirs = await make_project(client, other, "남의 것")

    mine_list = (await call(client, "GET", "", user)).json()
    their_list = (await call(client, "GET", "", other)).json()

    assert [p["id"] for p in mine_list] == [mine["id"]]
    assert [p["id"] for p in their_list] == [theirs["id"]]


async def test_list_hides_trashed_projects(client: httpx.AsyncClient, user: User) -> None:
    keep = await make_project(client, user, "유지")
    gone = await make_project(client, user, "삭제")
    await call(client, "DELETE", f"/{gone['id']}", user)

    response = await call(client, "GET", "", user)

    assert [p["id"] for p in response.json()] == [keep["id"]]


# --- GET /projects/{id} --------------------------------------------------------------------


async def test_get_returns_the_project(client: httpx.AsyncClient, user: User) -> None:
    created = await make_project(client, user, "조회", description="설명")

    response = await call(client, "GET", f"/{created['id']}", user)

    assert response.status_code == 200
    assert_project_shape(response.json())
    assert response.json() == created


async def test_get_a_missing_project_is_404(client: httpx.AsyncClient, user: User) -> None:
    response = await call(client, "GET", f"/{uuid.uuid4()}", user)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_get_someone_elses_project_is_403_without_leaking_its_data(
    client: httpx.AsyncClient, user: User, other: User
) -> None:
    secret = await make_project(client, other, "남의 비밀", description="남의 설명")

    response = await call(client, "GET", f"/{secret['id']}", user)

    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    assert "남의" not in response.text
    assert secret["id"] not in response.text


async def test_get_a_trashed_project_is_404_even_for_its_owner(
    client: httpx.AsyncClient, user: User
) -> None:
    created = await make_project(client, user)
    await call(client, "DELETE", f"/{created['id']}", user)

    response = await call(client, "GET", f"/{created['id']}", user)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
@pytest.mark.parametrize("bad_id", ["not-a-uuid", "123", "00000000-0000-0000", "' OR 1=1 --"])
async def test_a_malformed_project_id_is_a_validation_error(
    client: httpx.AsyncClient, user: User, method: str, bad_id: str
) -> None:
    body = {"title": "x"} if method == "PATCH" else None

    response = await call(client, method, f"/{bad_id}", user, json=body)

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


# --- PATCH /projects/{id} ------------------------------------------------------------------


async def test_patch_title_only_keeps_the_description(
    client: httpx.AsyncClient, user: User
) -> None:
    created = await make_project(client, user, "원래", description="설명")

    response = await call(client, "PATCH", f"/{created['id']}", user, json={"title": " 새 제목 "})

    assert response.status_code == 200
    body = response.json()
    assert_project_shape(body)
    assert body["title"] == "새 제목"
    assert body["description"] == "설명"
    assert body["id"] == created["id"]
    assert body["created_at"] == created["created_at"]
    assert body["last_activity_at"] == created["last_activity_at"]


async def test_patch_description_only_keeps_the_title(
    client: httpx.AsyncClient, user: User
) -> None:
    created = await make_project(client, user, "원래", description="설명")

    response = await call(
        client, "PATCH", f"/{created['id']}", user, json={"description": "새 설명"}
    )

    assert response.json()["title"] == "원래"
    assert response.json()["description"] == "새 설명"


async def test_patch_with_an_explicit_null_description_clears_it(
    client: httpx.AsyncClient, user: User
) -> None:
    created = await make_project(client, user, "원래", description="설명")

    response = await call(client, "PATCH", f"/{created['id']}", user, json={"description": None})

    assert response.status_code == 200
    assert response.json()["description"] is None
    assert response.json()["title"] == "원래"


async def test_patch_with_a_blank_description_clears_it(
    client: httpx.AsyncClient, user: User
) -> None:
    created = await make_project(client, user, "원래", description="설명")

    response = await call(client, "PATCH", f"/{created['id']}", user, json={"description": "  "})

    assert response.json()["description"] is None


async def test_patch_returns_the_updated_project_as_get_does(
    client: httpx.AsyncClient, user: User
) -> None:
    created = await make_project(client, user)

    patched = await call(client, "PATCH", f"/{created['id']}", user, json={"title": "바뀜"})
    fetched = await call(client, "GET", f"/{created['id']}", user)

    assert patched.json() == fetched.json()


async def test_patch_refreshes_updated_at_only(
    client: httpx.AsyncClient, user: User, session: AsyncSession
) -> None:
    created = await make_project(client, user)
    await session.execute(
        update(Project)
        .where(Project.id == uuid.UUID(created["id"]))
        .values(updated_at=OLD, last_activity_at=OLD)
    )
    session.expunge_all()

    response = await call(client, "PATCH", f"/{created['id']}", user, json={"title": "바뀜"})

    body = response.json()
    assert datetime.fromisoformat(body["updated_at"]) > OLD
    assert datetime.fromisoformat(body["last_activity_at"]) == OLD


@pytest.mark.parametrize("payload", [None, {}, {"unknown": 1}, {"user_id": "x", "id": "y"}])
async def test_patch_without_any_known_field_is_a_validation_error(
    client: httpx.AsyncClient, user: User, payload: Any
) -> None:
    created = await make_project(client, user)

    response = await call(client, "PATCH", f"/{created['id']}", user, json=payload)

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_patch_ignores_unknown_fields_next_to_a_valid_one(
    client: httpx.AsyncClient, user: User, other: User, session: AsyncSession
) -> None:
    created = await make_project(client, user)

    response = await call(
        client,
        "PATCH",
        f"/{created['id']}",
        user,
        json={"title": "바뀜", "user_id": str(other.id), "deletion_status": "trashed"},
    )

    assert response.status_code == 200
    row = (await session.execute(select(Project))).scalar_one()
    assert (row.user_id, row.deletion_status) == (user.id, "active")


@pytest.mark.parametrize("title", [None, "", "   "])
async def test_patch_with_a_null_or_blank_title_is_invalid(
    client: httpx.AsyncClient, user: User, title: str | None
) -> None:
    created = await make_project(client, user, "그대로")

    response = await call(client, "PATCH", f"/{created['id']}", user, json={"title": title})

    assert response.status_code == 422
    assert response.json() == TITLE_TOO_SHORT
    assert (await call(client, "GET", f"/{created['id']}", user)).json()["title"] == "그대로"


async def test_patch_with_too_long_values_is_invalid_and_changes_nothing(
    client: httpx.AsyncClient, user: User
) -> None:
    created = await make_project(client, user, "그대로", description="설명")

    long_title = await call(client, "PATCH", f"/{created['id']}", user, json={"title": "a" * 256})
    long_description = await call(
        client, "PATCH", f"/{created['id']}", user, json={"title": "새", "description": "a" * 2001}
    )

    assert (long_title.status_code, long_title.json()) == (422, TITLE_TOO_LONG)
    assert (long_description.status_code, long_description.json()) == (422, DESCRIPTION_TOO_LONG)
    assert (await call(client, "GET", f"/{created['id']}", user)).json() == created


@pytest.mark.parametrize("payload", [{"title": 5}, {"description": 5}, {"title": ["a"]}])
async def test_patch_with_mistyped_fields_is_a_validation_error(
    client: httpx.AsyncClient, user: User, payload: dict[str, Any]
) -> None:
    created = await make_project(client, user)

    response = await call(client, "PATCH", f"/{created['id']}", user, json=payload)

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_patch_a_missing_project_is_404(client: httpx.AsyncClient, user: User) -> None:
    response = await call(client, "PATCH", f"/{uuid.uuid4()}", user, json={"title": "x"})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_patch_someone_elses_project_is_403_and_changes_nothing(
    client: httpx.AsyncClient, user: User, other: User
) -> None:
    theirs = await make_project(client, other, "남의 것", description="남의 설명")

    response = await call(client, "PATCH", f"/{theirs['id']}", user, json={"title": "내 것"})

    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    assert (await call(client, "GET", f"/{theirs['id']}", other)).json() == theirs


async def test_patch_a_trashed_project_is_404(client: httpx.AsyncClient, user: User) -> None:
    created = await make_project(client, user)
    await call(client, "DELETE", f"/{created['id']}", user)

    response = await call(client, "PATCH", f"/{created['id']}", user, json={"title": "부활"})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_patch_checks_ownership_before_validating_the_values(
    client: httpx.AsyncClient, user: User, other: User
) -> None:
    theirs = await make_project(client, other)

    response = await call(client, "PATCH", f"/{theirs['id']}", user, json={"title": ""})

    assert response.status_code == 403


# --- DELETE /projects/{id} -----------------------------------------------------------------


async def test_delete_returns_204_with_no_body(client: httpx.AsyncClient, user: User) -> None:
    created = await make_project(client, user)

    response = await call(client, "DELETE", f"/{created['id']}", user)

    assert response.status_code == 204
    assert response.content == b""


async def test_delete_is_a_soft_delete(
    client: httpx.AsyncClient, user: User, session: AsyncSession
) -> None:
    created = await make_project(client, user)

    await call(client, "DELETE", f"/{created['id']}", user)

    row = (await session.execute(select(Project))).scalar_one()
    assert row.deletion_status == "trashed"
    assert row.trashed_at is not None
    assert row.scheduled_deletion_at is not None
    assert row.scheduled_deletion_at - row.trashed_at == timedelta(days=30)


async def test_deleting_twice_is_404_the_second_time(client: httpx.AsyncClient, user: User) -> None:
    created = await make_project(client, user)
    assert (await call(client, "DELETE", f"/{created['id']}", user)).status_code == 204

    response = await call(client, "DELETE", f"/{created['id']}", user)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_delete_a_missing_project_is_404(client: httpx.AsyncClient, user: User) -> None:
    response = await call(client, "DELETE", f"/{uuid.uuid4()}", user)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_delete_someone_elses_project_is_403_and_keeps_it(
    client: httpx.AsyncClient, user: User, other: User
) -> None:
    theirs = await make_project(client, other)

    response = await call(client, "DELETE", f"/{theirs['id']}", user)

    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    assert (await call(client, "GET", f"/{theirs['id']}", other)).status_code == 200


async def test_delete_only_removes_the_given_project(client: httpx.AsyncClient, user: User) -> None:
    keep = await make_project(client, user, "유지")
    gone = await make_project(client, user, "삭제")

    await call(client, "DELETE", f"/{gone['id']}", user)

    assert (await call(client, "GET", f"/{keep['id']}", user)).status_code == 200


# --- two users end to end -----------------------------------------------------------------


async def test_two_users_never_see_or_change_each_others_projects(
    client: httpx.AsyncClient, user: User, other: User
) -> None:
    a = await make_project(client, user, "A의 프로젝트")
    b = await make_project(client, other, "B의 프로젝트")

    assert (await call(client, "GET", f"/{b['id']}", user)).status_code == 403
    assert (
        await call(client, "PATCH", f"/{b['id']}", user, json={"title": "x"})
    ).status_code == 403
    assert (await call(client, "DELETE", f"/{b['id']}", user)).status_code == 403
    assert (await call(client, "GET", f"/{a['id']}", other)).status_code == 403
    assert (await call(client, "GET", f"/{a['id']}", user)).json() == a
    assert (await call(client, "GET", f"/{b['id']}", other)).json() == b


# --- OpenAPI -------------------------------------------------------------------------------


async def test_openapi_lists_the_five_operations(client: httpx.AsyncClient) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]

    assert set(paths[BASE]) == {"get", "post"}
    assert set(paths[f"{BASE}/{{project_id}}"]) == {"get", "patch", "delete"}
    assert "201" in paths[BASE]["post"]["responses"]
    assert "204" in paths[f"{BASE}/{{project_id}}"]["delete"]["responses"]
    assert paths[BASE]["get"]["tags"] == ["projects"]


# --- really committed (real get_session, a different session reads the result) -------------


@pytest.fixture
async def committed_factory(
    test_database_url: str, migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(test_database_url)
    factory = create_session_factory(engine)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: factory)
    yield factory
    async with factory() as cleanup:
        await cleanup.execute(delete(User))  # projects go with it (ON DELETE CASCADE)
        await cleanup.commit()
    await engine.dispose()


@pytest.fixture
async def committed_client(
    committed_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[httpx.AsyncClient]:
    async with http_client(build_app()) as c:
        yield c


async def committed_user(
    factory: async_sessionmaker[AsyncSession], email: str = "student@example.com"
) -> User:
    async with factory() as db:
        user = User(email=email, password_hash="$2b$12$hash")
        db.add(user)
        await db.commit()
    return user


async def read_project(
    factory: async_sessionmaker[AsyncSession], project_id: str
) -> Project | None:
    async with factory() as other_session:
        return (
            await other_session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
        ).scalar_one_or_none()


async def test_post_is_committed(
    committed_client: httpx.AsyncClient, committed_factory: async_sessionmaker[AsyncSession]
) -> None:
    user = await committed_user(committed_factory)
    created = await make_project(committed_client, user, "저장됨", description="설명")

    row = await read_project(committed_factory, created["id"])
    assert row is not None
    assert (row.title, row.description, row.user_id) == ("저장됨", "설명", user.id)


async def test_patch_is_committed(
    committed_client: httpx.AsyncClient, committed_factory: async_sessionmaker[AsyncSession]
) -> None:
    user = await committed_user(committed_factory)
    created = await make_project(committed_client, user, "원래", description="설명")

    response = await call(
        committed_client,
        "PATCH",
        f"/{created['id']}",
        user,
        json={"title": "바뀜", "description": None},
    )

    assert response.status_code == 200
    row = await read_project(committed_factory, created["id"])
    assert row is not None
    assert (row.title, row.description) == ("바뀜", None)
    assert row.updated_at > row.created_at


async def test_delete_is_committed(
    committed_client: httpx.AsyncClient, committed_factory: async_sessionmaker[AsyncSession]
) -> None:
    user = await committed_user(committed_factory)
    created = await make_project(committed_client, user)

    assert (await call(committed_client, "DELETE", f"/{created['id']}", user)).status_code == 204

    row = await read_project(committed_factory, created["id"])
    assert row is not None
    assert row.deletion_status == "trashed"
    assert row.trashed_at is not None
    assert row.scheduled_deletion_at is not None


async def test_a_refused_request_commits_nothing(
    committed_client: httpx.AsyncClient, committed_factory: async_sessionmaker[AsyncSession]
) -> None:
    user = await committed_user(committed_factory)
    intruder = await committed_user(committed_factory, "intruder@example.com")
    created = await make_project(committed_client, user, "그대로")

    assert (
        await call(committed_client, "DELETE", f"/{created['id']}", intruder)
    ).status_code == 403
    assert (
        await call(committed_client, "PATCH", f"/{created['id']}", intruder, json={"title": "x"})
    ).status_code == 403
    assert (await call(committed_client, "POST", "", user, json={"title": ""})).status_code == 422

    row = await read_project(committed_factory, created["id"])
    assert row is not None
    assert (row.title, row.deletion_status) == ("그대로", "active")
    async with committed_factory() as db:
        assert len((await db.execute(select(Project))).scalars().all()) == 1


async def test_data_is_committed_before_the_response_is_sent(
    committed_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await committed_user(committed_factory)
    app = build_app()
    visible_when_response_starts: list[bool] = []

    async def recording_app(
        scope: Any, receive: Any, send_message: Callable[..., Awaitable[None]]
    ) -> None:
        async def spying_send(message: Any) -> None:
            if message["type"] == "http.response.start" and scope["method"] == "POST":
                async with committed_factory() as other_session:
                    found = (await other_session.execute(select(Project))).scalars().all()
                visible_when_response_starts.append(len(found) == 1)
            await send_message(message)

        await app(scope, receive, spying_send)

    async with http_client(recording_app) as spying_client:
        assert (await call(spying_client, "POST", "", user, json={"title": "x"})).status_code == 201

    assert visible_when_response_starts == [True]


async def test_deleting_the_user_removes_the_projects_they_own(
    committed_client: httpx.AsyncClient, committed_factory: async_sessionmaker[AsyncSession]
) -> None:
    user = await committed_user(committed_factory)
    created = await make_project(committed_client, user)

    async with committed_factory() as db:
        await db.execute(delete(User).where(User.id == user.id))
        await db.commit()

    assert await read_project(committed_factory, created["id"]) is None
