from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.api.exceptions import AUTH_ERROR_STATUS, DOMAIN_ERROR_STATUS
from src.config import AppSettings
from src.main import create_app
from src.services.auth.errors import AuthError, InvalidEmailError, NotAuthenticatedError
from src.services.errors import DomainError
from src.services.project_errors import (
    InvalidProjectDescriptionError,
    InvalidProjectTitleError,
    ProjectForbiddenError,
    ProjectNotFoundError,
)


class UnmappedDomainError(DomainError):
    code = "something_else"
    default_message = "다른 도메인 오류입니다."


def test_domain_error_is_a_plain_exception_with_a_code_and_message() -> None:
    assert issubclass(DomainError, Exception)
    error = DomainError()
    assert error.code == "domain_error"
    assert error.message == error.default_message == str(error)
    assert DomainError("직접 쓴 메시지").message == "직접 쓴 메시지"
    assert str(DomainError("직접 쓴 메시지")) == "직접 쓴 메시지"


def test_domain_error_does_not_depend_on_the_api_layer() -> None:
    assert not any(base.__module__.startswith("src.api") for base in ProjectNotFoundError.__mro__)


def test_auth_error_is_a_domain_error_and_behaves_as_before() -> None:
    assert issubclass(AuthError, DomainError)
    assert AuthError().code == "auth_error"
    assert AuthError().message == "인증 처리 중 오류가 발생했습니다."
    assert InvalidEmailError("x").message == "x"
    assert NotAuthenticatedError().message == "로그인이 필요합니다."


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (
            ProjectNotFoundError(),
            "project_not_found",
            "요청한 프로젝트를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 프로젝트입니다.",
        ),
        (ProjectForbiddenError(), "project_forbidden", "이 프로젝트에 접근할 권한이 없습니다."),
        (InvalidProjectTitleError(), "invalid_project_title", "프로젝트 제목이 올바르지 않습니다."),
        (
            InvalidProjectDescriptionError(),
            "invalid_project_description",
            "프로젝트 설명이 올바르지 않습니다.",
        ),
    ],
)
def test_project_errors_have_stable_codes_and_korean_messages(
    error: DomainError, code: str, message: str
) -> None:
    assert isinstance(error, DomainError)
    assert not isinstance(error, AuthError)
    assert error.code == code
    assert error.message == message


def test_status_table_keeps_the_auth_mapping_and_adds_the_project_codes() -> None:
    assert AUTH_ERROR_STATUS == {
        "invalid_email": 422,
        "weak_password": 422,
        "email_already_registered": 409,
        "invalid_credentials": 401,
        "not_authenticated": 401,
        "session_expired": 401,
    }
    assert DOMAIN_ERROR_STATUS == {
        **AUTH_ERROR_STATUS,
        "project_not_found": 404,
        "project_forbidden": 403,
        "invalid_project_title": 422,
        "invalid_project_description": 422,
        "task_not_found": 404,
        "task_forbidden": 403,
        "code_not_found": 404,
        "code_file_missing": 404,
        "document_not_found": 404,
        "invalid_task_title": 422,
        "invalid_task_description": 422,
        "invalid_upload_method": 422,
        "no_files": 422,
        "too_many_files": 422,
        "invalid_file_path": 422,
        "language_required": 422,
        "unsupported_language": 422,
        "empty_code": 422,
    }


ERRORS: dict[str, DomainError] = {
    "not_found": ProjectNotFoundError(),
    "forbidden": ProjectForbiddenError(),
    "title": InvalidProjectTitleError(),
    "description": InvalidProjectDescriptionError(),
    "unmapped": UnmappedDomainError(),
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(AppSettings(_env_file=None))  # type: ignore[call-arg]

    @app.get("/t/raise/{name}")
    async def raise_error(name: str) -> None:
        raise ERRORS[name]

    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    ("name", "status", "code"),
    [
        ("not_found", 404, "project_not_found"),
        ("forbidden", 403, "project_forbidden"),
        ("title", 422, "invalid_project_title"),
        ("description", 422, "invalid_project_description"),
        ("unmapped", 400, "something_else"),
    ],
)
def test_domain_errors_become_the_right_http_response(
    client: TestClient, name: str, status: int, code: str
) -> None:
    response = client.get(f"/t/raise/{name}")

    assert response.status_code == status
    assert response.json() == {"error": code, "message": ERRORS[name].message}
