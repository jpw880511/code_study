import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies import ACCESS_TOKEN_COOKIE
from src.config import AppSettings
from src.db.session import get_session
from src.main import create_app
from src.models import CodeFile, Project, Task, User
from src.models.uploaded_code import MAX_UPLOAD_SIZE_BYTES
from src.utils.jwt import JWTSettings, create_access_token, get_jwt_settings

SETTINGS = JWTSettings(  # type: ignore[call-arg]
    _env_file=None, secret_key="a" * 40, refresh_secret_key="r" * 40
)
API = "/api/v1"
TITLE = "계산기 함수 학습"
TASK_KEYS = {
    "id",
    "project_id",
    "task_number",
    "title",
    "description",
    "upload_method",
    "created_at",
    "updated_at",
    "upload",
}
UPLOAD_KEYS = {
    "detected_language",
    "complexity_level",
    "total_lines",
    "total_files",
    "upload_size_bytes",
}
FILE_KEYS = {"id", "file_name", "file_path", "file_extension", "file_size_bytes", "mime_type"}
FORBIDDEN_KEYS = {
    "storage_path",
    "user_id",
    "deletion_status",
    "trashed_at",
    "scheduled_deletion_at",
    "uploaded_code_id",
}
OLD = datetime(2020, 1, 1, tzinfo=UTC)
NOT_AUTHENTICATED = {"error": "not_authenticated", "message": "로그인이 필요합니다."}
TASK_NOT_FOUND = {
    "error": "task_not_found",
    "message": "요청한 Task를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 Task입니다.",
}
TASK_FORBIDDEN = {"error": "task_forbidden", "message": "이 Task에 접근할 권한이 없습니다."}
PROJECT_NOT_FOUND = {
    "error": "project_not_found",
    "message": "요청한 프로젝트를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 프로젝트입니다.",
}
PROJECT_FORBIDDEN = {
    "error": "project_forbidden",
    "message": "이 프로젝트에 접근할 권한이 없습니다.",
}


def build_app(session: AsyncSession, storage_root: Path) -> FastAPI:
    app = create_app(
        AppSettings(_env_file=None, upload_storage_path=storage_root)  # type: ignore[call-arg]
    )

    async def use_test_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = use_test_session
    app.dependency_overrides[get_jwt_settings] = lambda: SETTINGS
    return app


def token_for(user: User) -> str:
    return create_access_token(str(user.id), settings=SETTINGS)


async def call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    user: User | None = None,
    **options: Any,
) -> httpx.Response:
    """A request carrying exactly one access cookie (the client's cookie jar is not used)."""
    client.cookies.clear()
    if user is not None:
        client.cookies.set(ACCESS_TOKEN_COOKIE, token_for(user), path="/")
    return await client.request(method, f"{API}{path}", **options)


def files_under(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
async def client(session: AsyncSession, root: Path) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=build_app(session, root))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def create_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def user(session: AsyncSession) -> User:
    return await create_user(session)


@pytest.fixture
async def other(session: AsyncSession) -> User:
    return await create_user(session, "other@example.com")


async def make_project(client: httpx.AsyncClient, user: User, title: str = "프로젝트") -> str:
    response = await call(client, "POST", "/projects", user, json={"title": title})
    assert response.status_code == 201
    return str(response.json()["id"])


@pytest.fixture
async def project_id(client: httpx.AsyncClient, user: User) -> str:
    return await make_project(client, user)


def paste_form(**overrides: Any) -> dict[str, Any]:
    form: dict[str, Any] = {
        "title": TITLE,
        "upload_method": "paste",
        "code": "print(1)\n",
        "language": "python",
    }
    form.update(overrides)
    return {k: v for k, v in form.items() if v is not None}


def part(name: str, content: bytes | str) -> tuple[str, tuple[str, bytes, str]]:
    data = content.encode() if isinstance(content, str) else content
    return ("files", (name, data, "application/octet-stream"))


async def create_task(
    client: httpx.AsyncClient,
    user: User,
    project_id: str,
    form: dict[str, Any] | None = None,
    files: list[Any] | None = None,
) -> httpx.Response:
    return await call(
        client,
        "POST",
        f"/projects/{project_id}/tasks",
        user,
        data=form if form is not None else paste_form(),
        files=files,
    )


async def new_task(
    client: httpx.AsyncClient, user: User, project_id: str, **form: Any
) -> dict[str, Any]:
    response = await create_task(client, user, project_id, paste_form(**form))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def assert_task_shape(body: dict[str, Any]) -> None:
    assert TASK_KEYS <= set(body)
    uuid.UUID(body["id"])
    uuid.UUID(body["project_id"])
    assert isinstance(body["task_number"], int)
    for key in ("created_at", "updated_at"):
        assert datetime.fromisoformat(body[key]).utcoffset() == timedelta(0), key
    if body["upload"] is not None:
        assert set(body["upload"]) == UPLOAD_KEYS


def assert_no_internal_keys(value: Any) -> None:
    if isinstance(value, dict):
        assert not FORBIDDEN_KEYS & set(value), set(value)
        for item in value.values():
            assert_no_internal_keys(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_internal_keys(item)


# --- authentication (every operation) ------------------------------------------------------

NIL = "00000000-0000-0000-0000-000000000000"
OPERATIONS = [
    ("GET", f"/projects/{NIL}/tasks", {}),
    ("POST", f"/projects/{NIL}/tasks", {"data": {"title": "x"}}),
    ("GET", f"/tasks/{NIL}", {}),
    ("PATCH", f"/tasks/{NIL}", {"json": {"title": "x"}}),
    ("DELETE", f"/tasks/{NIL}", {}),
    ("GET", f"/tasks/{NIL}/code", {}),
]


@pytest.mark.parametrize(("method", "path", "options"), OPERATIONS)
async def test_every_operation_needs_the_access_cookie(
    client: httpx.AsyncClient, method: str, path: str, options: dict[str, Any]
) -> None:
    response = await call(client, method, path, **options)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHENTICATED


# --- create: success -----------------------------------------------------------------------


async def test_paste_creates_a_task_with_the_full_response(
    client: httpx.AsyncClient, root: Path, user: User, project_id: str
) -> None:
    response = await create_task(
        client, user, project_id, paste_form(description="  메모  ", code="def f():\n    pass\n")
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == TASK_KEYS | {"files", "excluded_paths", "warnings"}
    assert_task_shape(body)
    assert_no_internal_keys(body)
    assert body["project_id"] == project_id
    assert (body["task_number"], body["title"], body["description"]) == (1, TITLE, "메모")
    assert body["upload_method"] == "paste"
    assert body["upload"] == {
        "detected_language": "python",
        "complexity_level": "beginner",
        "total_lines": 2,
        "total_files": 1,
        "upload_size_bytes": 18,
    }
    [file] = body["files"]
    assert set(file) == FILE_KEYS
    assert file["file_name"] == "pasted_code.py"
    assert file["file_path"] is None
    assert (file["file_extension"], file["file_size_bytes"]) == (".py", 18)
    assert file["mime_type"] == "text/x-python"
    assert (body["excluded_paths"], body["warnings"]) == ([], [])
    assert len(files_under(root)) == 1


async def test_file_upload_over_multipart(
    client: httpx.AsyncClient, root: Path, user: User, project_id: str
) -> None:
    response = await create_task(
        client,
        user,
        project_id,
        {"title": TITLE, "upload_method": "file", "paths": ["ignored/for/file.py"]},
        [part("main.py", "print(1)\n"), part("App.jsx", "export {}\n")],
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["upload_method"] == "file"
    assert body["upload"]["total_files"] == 2
    assert [f["file_name"] for f in body["files"]] == ["App.jsx", "main.py"]
    assert all(f["file_path"] is None for f in body["files"])
    assert len(files_under(root)) == 2


async def test_folder_upload_keeps_paths_and_reports_excluded_ones(
    client: httpx.AsyncClient, root: Path, user: User, project_id: str
) -> None:
    paths = ["my-app/src/App.jsx", "my-app/.git/config", "my-app/node_modules/a/index.js"]
    response = await create_task(
        client,
        user,
        project_id,
        {"title": TITLE, "upload_method": "folder", "paths": paths},
        [part("App.jsx", "export {}\n"), part("config", "[core]"), part("index.js", "1")],
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["excluded_paths"] == ["my-app/.git/config", "my-app/node_modules/a/index.js"]
    [file] = body["files"]
    assert (file["file_name"], file["file_path"]) == ("App.jsx", "my-app/src/App.jsx")
    assert file["mime_type"] == "text/javascript"
    assert len(files_under(root)) == 1


async def test_a_large_paste_comes_with_the_warning(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    body = await new_task(client, user, project_id, code="x = 1\n" * 501)

    assert [w["code"] for w in body["warnings"]] == ["large_code"]
    assert body["warnings"][0]["message"].startswith("큰 코드 파일이 감지되었습니다.")
    assert set(body["warnings"][0]) == {"code", "message"}


async def test_a_paste_larger_than_a_megabyte_is_accepted(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    code = "x = 1\n" * 400_000  # about 2.4 MB: more than a default form field may hold

    response = await create_task(client, user, project_id, paste_form(code=code))

    assert response.status_code == 201, response.text
    assert response.json()["upload"]["upload_size_bytes"] == len(code)


async def test_a_paste_of_11mb_is_refused_as_too_large(
    client: httpx.AsyncClient, session: AsyncSession, user: User, project_id: str
) -> None:
    code = "x = 1\n" * 1_900_000  # about 11.4 MB

    response = await create_task(client, user, project_id, paste_form(code=code))

    assert response.status_code == 413
    assert response.json()["error"] == "file_too_large"
    assert (await session.execute(select(Task))).first() is None


async def test_task_numbers_count_up_and_the_project_activity_moves_forward(
    client: httpx.AsyncClient, session: AsyncSession, user: User, project_id: str
) -> None:
    await session.execute(
        update(Project).where(Project.id == uuid.UUID(project_id)).values(last_activity_at=OLD)
    )
    first = await new_task(client, user, project_id)
    second = await new_task(client, user, project_id)

    assert (first["task_number"], second["task_number"]) == (1, 2)
    project = await call(client, "GET", f"/projects/{project_id}", user)
    assert datetime.fromisoformat(project.json()["last_activity_at"]) > OLD


async def test_a_created_task_is_stored_with_its_internal_columns(
    client: httpx.AsyncClient, session: AsyncSession, user: User, project_id: str
) -> None:
    body = await new_task(client, user, project_id)

    task = (
        await session.execute(select(Task).where(Task.id == uuid.UUID(body["id"])))
    ).scalar_one()
    code_file = (await session.execute(select(CodeFile))).scalar_one()
    assert task.deletion_status == "active"
    assert code_file.storage_path.startswith(f"{user.id}/{task.id}/")


# --- create: errors ------------------------------------------------------------------------

LONG_TITLE = "a" * 256
EXE = [part("tool.exe", "MZ")]

ERROR_CASES: list[tuple[str, dict[str, Any], list[Any] | None, int, str, str]] = [
    (
        "bad_method",
        paste_form(upload_method="zip"),
        None,
        422,
        "invalid_upload_method",
        "업로드 방식이 올바르지 않습니다. file, folder, paste 중 하나를 선택하세요.",
    ),
    (
        "title_short",
        paste_form(title="짧음"),
        None,
        422,
        "invalid_task_title",
        "Task 제목은 최소 5자 이상이어야 합니다.",
    ),
    (
        "title_blank",
        paste_form(title="      "),
        None,
        422,
        "invalid_task_title",
        "Task 제목은 최소 5자 이상이어야 합니다.",
    ),
    (
        "title_long",
        paste_form(title=LONG_TITLE),
        None,
        422,
        "invalid_task_title",
        "Task 제목은 최대 255자까지 입력 가능합니다.",
    ),
    (
        "title_nul",
        paste_form(title="제목\x00입니다"),
        None,
        422,
        "invalid_task_title",
        "Task 제목에 사용할 수 없는 문자가 포함되어 있습니다.",
    ),
    (
        "description_long",
        paste_form(description="가" * 501),
        None,
        422,
        "invalid_task_description",
        "Task 설명은 최대 500자까지 입력 가능합니다.",
    ),
    (
        "description_nul",
        paste_form(description="설명\x00"),
        None,
        422,
        "invalid_task_description",
        "Task 설명에 사용할 수 없는 문자가 포함되어 있습니다.",
    ),
    (
        "no_language",
        paste_form(language=None),
        None,
        422,
        "language_required",
        "업로드하기 전에 프로그래밍 언어를 선택하세요.",
    ),
    (
        "bad_language",
        paste_form(language="rust"),
        None,
        422,
        "unsupported_language",
        "지원하지 않는 프로그래밍 언어입니다.",
    ),
    (
        "empty_code",
        paste_form(code="  \n"),
        None,
        422,
        "empty_code",
        "붙여넣은 코드가 비어 있습니다.",
    ),
    (
        "no_files",
        {"title": TITLE, "upload_method": "file"},
        None,
        422,
        "no_files",
        "업로드할 파일을 선택하세요.",
    ),
    (
        "too_many",
        {"title": TITLE, "upload_method": "file"},
        [part(f"f{i}.py", "x = 1\n") for i in range(21)],
        422,
        "too_many_files",
        "업로드당 최대 20개 파일까지 가능합니다. 파일 수를 줄이거나 폴더 업로드를 사용하세요.",
    ),
    (
        "paths_mismatch",
        {"title": TITLE, "upload_method": "folder", "paths": ["a/x.py"]},
        [part("x.py", "x"), part("y.py", "y")],
        422,
        "invalid_file_path",
        "파일 경로가 올바르지 않습니다.",
    ),
    (
        "path_traversal",
        {"title": TITLE, "upload_method": "folder", "paths": ["../../etc/x.py"]},
        [part("x.py", "x")],
        422,
        "invalid_file_path",
        "파일 경로가 올바르지 않습니다.",
    ),
    (
        "path_absolute",
        {"title": TITLE, "upload_method": "folder", "paths": ["/etc/x.py"]},
        [part("x.py", "x")],
        422,
        "invalid_file_path",
        "파일 경로가 올바르지 않습니다.",
    ),
    (
        "path_backslash",
        {"title": TITLE, "upload_method": "folder", "paths": ["a\\x.py"]},
        [part("x.py", "x")],
        422,
        "invalid_file_path",
        "파일 경로가 올바르지 않습니다.",
    ),
    (
        "all_excluded",
        {"title": TITLE, "upload_method": "folder", "paths": ["app/.git/config"]},
        [part("config", "x")],
        422,
        "no_files",
        "업로드할 파일을 선택하세요.",
    ),
    (
        "unsupported_type",
        {"title": TITLE, "upload_method": "file"},
        EXE,
        415,
        "unsupported_file_type",
        "지원하지 않는 파일 형식입니다 (.exe).",
    ),
    (
        "binary",
        {"title": TITLE, "upload_method": "file"},
        [part("fake.py", b"\x89PNG\r\n\x1a\n\x00\x00")],
        415,
        "binary_file_rejected",
        "바이너리 파일은 업로드할 수 없습니다.",
    ),
    (
        "file_11mb",
        {"title": TITLE, "upload_method": "file"},
        [part("big.py", b"a" * (11 * 1024 * 1024))],
        413,
        "file_too_large",
        "파일 크기가 10MB를 초과합니다.",
    ),
    (
        "total_over",
        {"title": TITLE, "upload_method": "file"},
        [part("a.py", b"x = 1\n" * 1_000_000), part("b.py", b"x = 1\n" * 1_000_000)],
        413,
        "file_too_large",
        "업로드한 파일의 전체 크기가 10MB를 초과합니다.",
    ),
]


@pytest.mark.parametrize(
    ("form", "files", "status", "code", "message"),
    [case[1:] for case in ERROR_CASES],
    ids=[case[0] for case in ERROR_CASES],
)
async def test_a_refused_upload_stores_nothing(
    client: httpx.AsyncClient,
    session: AsyncSession,
    root: Path,
    user: User,
    project_id: str,
    form: dict[str, Any],
    files: list[Any] | None,
    status: int,
    code: str,
    message: str,
) -> None:
    response = await create_task(client, user, project_id, form, files)

    assert response.status_code == status, response.text
    body = response.json()
    assert (body["error"], body["message"]) == (code, message)
    assert (await session.execute(select(Task))).first() is None
    assert (await session.execute(select(CodeFile))).first() is None
    assert not root.exists() or list(root.rglob("*")) == []


async def test_a_too_large_file_carries_the_validators_details_and_suggestion(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    response = await create_task(
        client,
        user,
        project_id,
        {"title": TITLE, "upload_method": "file"},
        [part("big.py", b"a" * (MAX_UPLOAD_SIZE_BYTES + 1))],
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": "file_too_large",
        "message": "파일 크기가 10MB를 초과합니다.",
        "details": {"max_size_mb": 10, "uploaded_size_mb": 10.0},
        "suggestion": "더 작은 파일을 선택하거나 코드를 여러 태스크로 나누어 업로드하세요.",
    }


async def test_an_unsupported_file_carries_details_and_suggestion(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    response = await create_task(
        client, user, project_id, {"title": TITLE, "upload_method": "file"}, EXE
    )

    body = response.json()
    assert response.status_code == 415
    assert body["details"]["extension"] == ".exe"
    assert ".py" in body["details"]["supported_extensions"]
    assert body["suggestion"].startswith(".py, .js")


async def test_a_binary_file_carries_a_suggestion(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    response = await create_task(
        client,
        user,
        project_id,
        {"title": TITLE, "upload_method": "file"},
        [part("fake.py", b"\x00\x01")],
    )

    assert response.status_code == 415
    assert set(response.json()) == {"error", "message", "suggestion"}


@pytest.mark.parametrize("missing", ["title", "upload_method"])
async def test_a_form_without_a_required_field_is_a_validation_error(
    client: httpx.AsyncClient, user: User, project_id: str, missing: str
) -> None:
    form = paste_form()
    del form[missing]

    response = await create_task(client, user, project_id, form)

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_a_malformed_project_id_is_a_validation_error(
    client: httpx.AsyncClient, user: User
) -> None:
    response = await create_task(client, user, "not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_create_in_foreign_trashed_or_missing_project(
    client: httpx.AsyncClient, user: User, other: User, project_id: str
) -> None:
    foreign = await create_task(client, other, project_id)
    assert (foreign.status_code, foreign.json()) == (403, PROJECT_FORBIDDEN)

    missing = await create_task(client, user, str(uuid.uuid4()))
    assert (missing.status_code, missing.json()) == (404, PROJECT_NOT_FOUND)

    await call(client, "DELETE", f"/projects/{project_id}", user)
    trashed = await create_task(client, user, project_id)
    assert (trashed.status_code, trashed.json()) == (404, PROJECT_NOT_FOUND)


async def test_a_foreign_project_is_forbidden_even_for_an_invalid_form(
    client: httpx.AsyncClient, other: User, project_id: str
) -> None:
    response = await create_task(client, other, project_id, paste_form(title="짧음"))

    assert response.status_code == 403


# --- list ----------------------------------------------------------------------------------


async def test_list_is_a_bare_array_in_ascending_task_number_order(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    ids = [
        (await new_task(client, user, project_id, title=f"태스크 번호 {i}"))["id"]
        for i in (1, 2, 3)
    ]

    response = await call(client, "GET", f"/projects/{project_id}/tasks", user)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert [t["id"] for t in body] == ids
    assert [t["task_number"] for t in body] == [1, 2, 3]
    for item in body:
        assert set(item) == TASK_KEYS
        assert_task_shape(item)
        assert item["upload"]["total_files"] == 1
    assert_no_internal_keys(body)


async def test_list_hides_trashed_tasks_and_other_projects(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    other_project = await make_project(client, user, "다른 프로젝트")
    keep = await new_task(client, user, project_id)
    gone = await new_task(client, user, project_id)
    await new_task(client, user, other_project)
    await call(client, "DELETE", f"/tasks/{gone['id']}", user)

    response = await call(client, "GET", f"/projects/{project_id}/tasks", user)

    assert [t["id"] for t in response.json()] == [keep["id"]]


async def test_list_of_a_project_without_tasks_is_an_empty_array(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    response = await call(client, "GET", f"/projects/{project_id}/tasks", user)

    assert (response.status_code, response.json()) == (200, [])


async def test_list_follows_the_project_rules(
    client: httpx.AsyncClient, user: User, other: User, project_id: str
) -> None:
    foreign = await call(client, "GET", f"/projects/{project_id}/tasks", other)
    assert (foreign.status_code, foreign.json()) == (403, PROJECT_FORBIDDEN)

    missing = await call(client, "GET", f"/projects/{uuid.uuid4()}/tasks", user)
    assert (missing.status_code, missing.json()) == (404, PROJECT_NOT_FOUND)

    await call(client, "DELETE", f"/projects/{project_id}", user)
    trashed = await call(client, "GET", f"/projects/{project_id}/tasks", user)
    assert (trashed.status_code, trashed.json()) == (404, PROJECT_NOT_FOUND)


# --- get -----------------------------------------------------------------------------------


async def test_get_returns_the_detail_with_sorted_files(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    created = await create_task(
        client,
        user,
        project_id,
        {
            "title": TITLE,
            "upload_method": "folder",
            "paths": ["app/z.py", "app/a/b.js", "app/README.md"],
        },
        [part("z.py", "z = 1\n"), part("b.js", "1"), part("README.md", "# hi\n")],
    )

    response = await call(client, "GET", f"/tasks/{created.json()['id']}", user)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == TASK_KEYS | {"files"}
    assert_task_shape(body)
    assert_no_internal_keys(body)
    assert [f["file_path"] for f in body["files"]] == ["app/README.md", "app/a/b.js", "app/z.py"]
    assert all(set(f) == FILE_KEYS for f in body["files"])
    assert body["upload"]["total_files"] == 3


async def test_get_of_a_task_without_files_has_a_null_upload_and_no_files(
    client: httpx.AsyncClient, session: AsyncSession, user: User, project_id: str
) -> None:
    task = Task(project_id=uuid.UUID(project_id), task_number=1, title=TITLE)
    session.add(task)
    await session.flush()

    response = await call(client, "GET", f"/tasks/{task.id}", user)

    body = response.json()
    assert (body["upload"], body["upload_method"], body["files"]) == (None, None, [])


async def test_get_follows_the_task_rules(
    client: httpx.AsyncClient, user: User, other: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id)

    foreign = await call(client, "GET", f"/tasks/{task['id']}", other)
    assert (foreign.status_code, foreign.json()) == (403, TASK_FORBIDDEN)

    missing = await call(client, "GET", f"/tasks/{uuid.uuid4()}", user)
    assert (missing.status_code, missing.json()) == (404, TASK_NOT_FOUND)

    malformed = await call(client, "GET", "/tasks/not-a-uuid", user)
    assert (malformed.status_code, malformed.json()["error"]) == (422, "validation_error")


# --- patch ---------------------------------------------------------------------------------


async def test_patch_changes_only_the_sent_fields(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id, description="원래 설명")
    url = f"/tasks/{task['id']}"

    renamed = await call(client, "PATCH", url, user, json={"title": "  바뀐 제목입니다 "})
    assert renamed.status_code == 200
    body = renamed.json()
    assert set(body) == TASK_KEYS
    assert_task_shape(body)
    assert_no_internal_keys(body)
    assert (body["title"], body["description"]) == ("바뀐 제목입니다", "원래 설명")
    assert (body["task_number"], body["upload_method"]) == (1, "paste")
    assert body["upload"]["total_files"] == 1
    assert body["updated_at"] >= task["updated_at"]

    described = await call(client, "PATCH", url, user, json={"description": "새 설명"})
    assert (described.json()["title"], described.json()["description"]) == (
        "바뀐 제목입니다",
        "새 설명",
    )


async def test_patch_with_a_null_description_clears_it(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id, description="지울 설명")

    response = await call(client, "PATCH", f"/tasks/{task['id']}", user, json={"description": None})

    assert response.json()["description"] is None


@pytest.mark.parametrize(
    ("body", "code", "message"),
    [
        ({"title": "짧음"}, "invalid_task_title", "Task 제목은 최소 5자 이상이어야 합니다."),
        ({"title": None}, "invalid_task_title", "Task 제목은 최소 5자 이상이어야 합니다."),
        (
            {"title": "a" * 256},
            "invalid_task_title",
            "Task 제목은 최대 255자까지 입력 가능합니다.",
        ),
        (
            {"description": "가" * 501},
            "invalid_task_description",
            "Task 설명은 최대 500자까지 입력 가능합니다.",
        ),
    ],
)
async def test_patch_refuses_invalid_values_and_changes_nothing(
    client: httpx.AsyncClient,
    user: User,
    project_id: str,
    body: dict[str, Any],
    code: str,
    message: str,
) -> None:
    task = await new_task(client, user, project_id, description="그대로")

    response = await call(client, "PATCH", f"/tasks/{task['id']}", user, json=body)

    assert response.status_code == 422
    assert response.json() == {"error": code, "message": message}
    unchanged = await call(client, "GET", f"/tasks/{task['id']}", user)
    assert (unchanged.json()["title"], unchanged.json()["description"]) == (TITLE, "그대로")


@pytest.mark.parametrize("body", [{}, {"task_number": 9}, None])
async def test_patch_needs_title_or_description(
    client: httpx.AsyncClient, user: User, project_id: str, body: dict[str, Any] | None
) -> None:
    task = await new_task(client, user, project_id)

    response = await call(client, "PATCH", f"/tasks/{task['id']}", user, json=body)

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_patch_cannot_change_the_number_or_the_upload(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id)

    response = await call(
        client,
        "PATCH",
        f"/tasks/{task['id']}",
        user,
        json={"title": "바뀐 제목입니다", "task_number": 9, "upload_method": "file"},
    )

    assert response.status_code == 200
    assert (response.json()["task_number"], response.json()["upload_method"]) == (1, "paste")


async def test_patch_follows_the_task_rules(
    client: httpx.AsyncClient, user: User, other: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id)
    url = f"/tasks/{task['id']}"
    body = {"title": "바뀐 제목입니다"}

    foreign = await call(client, "PATCH", url, other, json=body)
    assert (foreign.status_code, foreign.json()) == (403, TASK_FORBIDDEN)

    missing = await call(client, "PATCH", f"/tasks/{uuid.uuid4()}", user, json=body)
    assert (missing.status_code, missing.json()) == (404, TASK_NOT_FOUND)

    await call(client, "DELETE", url, user)
    trashed = await call(client, "PATCH", url, user, json=body)
    assert (trashed.status_code, trashed.json()) == (404, TASK_NOT_FOUND)


# --- delete --------------------------------------------------------------------------------


async def test_delete_is_a_204_that_hides_the_task_but_keeps_its_files_and_number(
    client: httpx.AsyncClient, session: AsyncSession, root: Path, user: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id)

    response = await call(client, "DELETE", f"/tasks/{task['id']}", user)

    assert (response.status_code, response.content) == (204, b"")
    assert (await call(client, "GET", f"/tasks/{task['id']}", user)).status_code == 404
    assert (await call(client, "GET", f"/tasks/{task['id']}/code", user)).status_code == 404
    assert (await call(client, "GET", f"/projects/{project_id}/tasks", user)).json() == []
    row = (await session.execute(select(Task).where(Task.id == uuid.UUID(task["id"])))).scalar_one()
    assert row.deletion_status == "trashed"
    assert row.scheduled_deletion_at - row.trashed_at == timedelta(days=30)
    assert len(files_under(root)) == 1
    again = await new_task(client, user, project_id)
    assert again["task_number"] == 2


async def test_delete_follows_the_task_rules(
    client: httpx.AsyncClient, user: User, other: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id)
    url = f"/tasks/{task['id']}"

    foreign = await call(client, "DELETE", url, other)
    assert (foreign.status_code, foreign.json()) == (403, TASK_FORBIDDEN)
    assert (await call(client, "DELETE", url, user)).status_code == 204
    again = await call(client, "DELETE", url, user)
    assert (again.status_code, again.json()) == (404, TASK_NOT_FOUND)


async def test_deleting_a_project_trashes_its_tasks_too(
    client: httpx.AsyncClient, session: AsyncSession, user: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id)

    await call(client, "DELETE", f"/projects/{project_id}", user)

    url = f"/tasks/{task['id']}"
    responses = [
        await call(client, "GET", url, user),
        await call(client, "GET", f"{url}/code", user),
        await call(client, "PATCH", url, user, json={"title": "바뀐 제목입니다"}),
        await call(client, "DELETE", url, user),
    ]
    for response in responses:
        assert (response.status_code, response.json()) == (404, TASK_NOT_FOUND)
    row = (await session.execute(select(Task).where(Task.id == uuid.UUID(task["id"])))).scalar_one()
    assert row.deletion_status == "trashed"


# --- code ----------------------------------------------------------------------------------


async def test_code_returns_the_files_with_language_and_content(
    client: httpx.AsyncClient, user: User, project_id: str
) -> None:
    created = await create_task(
        client,
        user,
        project_id,
        {"title": TITLE, "upload_method": "folder", "paths": ["app/b.py", "app/a.js"]},
        [part("b.py", "print('안녕')\n"), part("a.js", "const a = 1;\n")],
    )

    response = await call(client, "GET", f"/tasks/{created.json()['id']}/code", user)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"files"}
    assert_no_internal_keys(body)
    assert [f["file_path"] for f in body["files"]] == ["app/a.js", "app/b.py"]
    assert [f["language"] for f in body["files"]] == ["javascript", "python"]
    assert [f["content"] for f in body["files"]] == ["const a = 1;\n", "print('안녕')\n"]
    for file in body["files"]:
        assert set(file) == FILE_KEYS | {"language", "content"}
        assert file["file_size_bytes"] == len(file["content"].encode())


async def test_code_of_a_task_without_an_upload_is_code_not_found(
    client: httpx.AsyncClient, session: AsyncSession, user: User, project_id: str
) -> None:
    task = Task(project_id=uuid.UUID(project_id), task_number=1, title=TITLE)
    session.add(task)
    await session.flush()

    response = await call(client, "GET", f"/tasks/{task.id}/code", user)

    assert response.status_code == 404
    assert response.json() == {
        "error": "code_not_found",
        "message": "이 Task에는 업로드된 코드가 없습니다.",
    }


async def test_code_with_a_file_gone_from_disk_is_code_file_missing(
    client: httpx.AsyncClient, root: Path, user: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id)
    files_under(root)[0].unlink()

    response = await call(client, "GET", f"/tasks/{task['id']}/code", user)

    assert response.status_code == 404
    assert response.json() == {
        "error": "code_file_missing",
        "message": "저장된 코드 파일을 찾을 수 없습니다.",
    }


async def test_code_follows_the_task_rules(
    client: httpx.AsyncClient, user: User, other: User, project_id: str
) -> None:
    task = await new_task(client, user, project_id)

    foreign = await call(client, "GET", f"/tasks/{task['id']}/code", other)
    assert (foreign.status_code, foreign.json()) == (403, TASK_FORBIDDEN)

    missing = await call(client, "GET", f"/tasks/{uuid.uuid4()}/code", user)
    assert (missing.status_code, missing.json()) == (404, TASK_NOT_FOUND)
