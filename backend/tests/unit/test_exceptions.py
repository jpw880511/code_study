import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from src.api.exceptions import (
    ERROR_MESSAGES,
    AppError,
    ConflictError,
    ErrorResponse,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from src.config import AppSettings
from src.main import create_app

ALLOWED = "http://localhost:5173"
SECRET_ERROR_TEXT = "database password is hunter2"


class EditConflictError(AppError):
    status_code = 409
    error = "edit_conflict"


class Payload(BaseModel):
    name: str
    age: int


def build_app() -> FastAPI:
    app = create_app(AppSettings(allowed_origins=[ALLOWED], _env_file=None))  # type: ignore[call-arg]

    @app.get("/t/not-found")
    async def not_found() -> None:
        raise NotFoundError()

    @app.get("/t/custom-message")
    async def custom_message() -> None:
        raise NotFoundError("프로젝트를 찾을 수 없습니다.")

    @app.get("/t/details")
    async def details() -> None:
        raise ConflictError(details={"project_id": "p1"}, suggestion="새로고침 후 다시 시도하세요.")

    @app.get("/t/edit-conflict")
    async def edit_conflict() -> None:
        raise EditConflictError("이 프로젝트가 다른 곳에서 수정되었습니다.")

    @app.get("/t/unauthorized")
    async def unauthorized() -> None:
        raise UnauthorizedError()

    @app.get("/t/forbidden")
    async def forbidden() -> None:
        raise ForbiddenError()

    @app.get("/t/http-400")
    async def http_400() -> None:
        raise HTTPException(status_code=400, detail="이메일이 이미 사용 중입니다.")

    @app.get("/t/http-401")
    async def http_401() -> None:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})

    @app.get("/t/http-503")
    async def http_503() -> None:
        raise HTTPException(status_code=503)

    @app.get("/t/http-599")
    async def http_599() -> None:
        raise HTTPException(status_code=599, detail="custom upstream failure")

    @app.post("/t/validate")
    async def validate(payload: Payload) -> Payload:
        return payload

    @app.get("/t/boom")
    async def boom() -> None:
        raise RuntimeError(SECRET_ERROR_TEXT)

    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(build_app()) as test_client:
        yield test_client


def test_app_error_body_has_error_and_message_only_by_default(client: TestClient) -> None:
    response = client.get("/t/not-found")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"error": "not_found", "message": ERROR_MESSAGES["not_found"]}


def test_app_error_custom_message(client: TestClient) -> None:
    assert client.get("/t/custom-message").json()["message"] == "프로젝트를 찾을 수 없습니다."


def test_app_error_details_and_suggestion(client: TestClient) -> None:
    response = client.get("/t/details")
    assert response.status_code == 409
    assert response.json() == {
        "error": "conflict",
        "message": ERROR_MESSAGES["conflict"],
        "details": {"project_id": "p1"},
        "suggestion": "새로고침 후 다시 시도하세요.",
    }


def test_custom_error_subclass_defines_its_own_code(client: TestClient) -> None:
    response = client.get("/t/edit-conflict")
    assert response.status_code == 409
    assert response.json() == {
        "error": "edit_conflict",
        "message": "이 프로젝트가 다른 곳에서 수정되었습니다.",
    }


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [("/t/unauthorized", 401, "unauthorized"), ("/t/forbidden", 403, "forbidden")],
)
def test_auth_errors(client: TestClient, path: str, status: int, code: str) -> None:
    response = client.get(path)
    assert response.status_code == status
    assert response.json() == {"error": code, "message": ERROR_MESSAGES[code]}


def test_unknown_route_uses_error_format(client: TestClient) -> None:
    response = client.get("/t/missing")
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "message": ERROR_MESSAGES["not_found"]}


def test_wrong_method_uses_error_format(client: TestClient) -> None:
    response = client.post("/t/not-found")
    assert response.status_code == 405
    assert response.json()["error"] == "method_not_allowed"
    assert "allow" in response.headers


def test_http_exception_detail_is_kept_in_details(client: TestClient) -> None:
    response = client.get("/t/http-400")
    assert response.status_code == 400
    assert response.json() == {
        "error": "bad_request",
        "message": ERROR_MESSAGES["bad_request"],
        "details": {"detail": "이메일이 이미 사용 중입니다."},
    }


def test_http_exception_headers_are_preserved(client: TestClient) -> None:
    response = client.get("/t/http-401")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"error": "unauthorized", "message": ERROR_MESSAGES["unauthorized"]}


def test_other_server_http_exceptions_use_generic_code(client: TestClient) -> None:
    response = client.get("/t/http-503")
    assert response.status_code == 503
    assert response.json()["error"] == "http_error"


def test_non_standard_status_code_is_handled(client: TestClient) -> None:
    response = client.get("/t/http-599")
    assert response.status_code == 599
    assert response.json() == {
        "error": "http_error",
        "message": ERROR_MESSAGES["http_error"],
        "details": {"detail": "custom upstream failure"},
    }


def test_validation_error_lists_fields_without_echoing_input(client: TestClient) -> None:
    response = client.post("/t/validate", json={"name": "supersecret-token", "age": "abc"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["message"] == ERROR_MESSAGES["validation_error"]
    errors = body["details"]["errors"]
    assert [e["field"] for e in errors] == ["body.age"]
    assert set(errors[0]) == {"field", "message", "type"}
    assert "supersecret-token" not in response.text
    assert "abc" not in response.text


def test_validation_error_reports_missing_fields(client: TestClient) -> None:
    response = client.post("/t/validate", json={})
    fields = sorted(e["field"] for e in response.json()["details"]["errors"])
    assert fields == ["body.age", "body.name"]


def test_unhandled_exception_returns_generic_500(client: TestClient) -> None:
    response = client.get("/t/boom")
    assert response.status_code == 500
    assert response.json() == {
        "error": "internal_error",
        "message": ERROR_MESSAGES["internal_error"],
    }
    assert SECRET_ERROR_TEXT not in response.text
    assert "Traceback" not in response.text


def test_unhandled_exception_is_logged_with_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="src.api.exceptions"):
        response = client.get("/t/boom", headers={"X-Request-ID": "trace-500"})
    assert response.headers["x-request-id"] == "trace-500"
    record = next(r for r in caplog.records if r.name == "src.api.exceptions")
    assert "trace-500" in record.getMessage()
    assert record.exc_info is not None
    assert SECRET_ERROR_TEXT in str(record.exc_info[1])


def test_500_responses_still_carry_cors_and_request_headers(client: TestClient) -> None:
    response = client.get("/t/boom", headers={"Origin": ALLOWED})
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert "x-request-id" in response.headers
    assert "x-process-time" in response.headers


def test_error_messages_are_centralized_and_korean() -> None:
    expected = {
        "bad_request",
        "unauthorized",
        "forbidden",
        "not_found",
        "method_not_allowed",
        "conflict",
        "validation_error",
        "http_error",
        "internal_error",
    }
    assert expected <= set(ERROR_MESSAGES)
    for message in ERROR_MESSAGES.values():
        assert any("가" <= ch <= "힣" for ch in message), message


def test_error_response_schema() -> None:
    assert ErrorResponse(error="x", message="y").model_dump(exclude_none=True) == {
        "error": "x",
        "message": "y",
    }
    with pytest.raises(ValidationError):
        ErrorResponse(message="missing error code")  # type: ignore[call-arg]
