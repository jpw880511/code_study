from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.config import AppSettings
from src.main import create_app
from src.services.auth.errors import (
    AuthError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidEmailError,
    NotAuthenticatedError,
    SessionExpiredError,
    WeakPasswordError,
)


class UnmappedAuthError(AuthError):
    code = "something_new"
    default_message = "새로운 인증 오류입니다."


ERRORS: dict[str, AuthError] = {
    "invalid_email": InvalidEmailError(),
    "weak_password": WeakPasswordError(),
    "email_already_registered": EmailAlreadyRegisteredError(),
    "invalid_credentials": InvalidCredentialsError(),
    "not_authenticated": NotAuthenticatedError(),
    "session_expired": SessionExpiredError(),
    "unmapped": UnmappedAuthError(),
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
        ("invalid_email", 422, "invalid_email"),
        ("weak_password", 422, "weak_password"),
        ("email_already_registered", 409, "email_already_registered"),
        ("invalid_credentials", 401, "invalid_credentials"),
        ("not_authenticated", 401, "not_authenticated"),
        ("session_expired", 401, "session_expired"),
    ],
)
def test_each_auth_error_becomes_the_right_http_response(
    client: TestClient, name: str, status: int, code: str
) -> None:
    response = client.get(f"/t/raise/{name}")

    assert response.status_code == status
    assert response.json() == {"error": code, "message": ERRORS[name].message}


def test_an_auth_error_without_a_mapping_is_a_client_error_not_a_server_error(
    client: TestClient,
) -> None:
    response = client.get("/t/raise/unmapped")
    assert response.status_code == 400
    assert response.json() == {"error": "something_new", "message": "새로운 인증 오류입니다."}


def test_auth_error_responses_carry_the_usual_headers(client: TestClient) -> None:
    response = client.get("/t/raise/not_authenticated", headers={"X-Request-ID": "trace-401"})
    assert response.headers["x-request-id"] == "trace-401"
    assert response.headers["content-type"].startswith("application/json")
