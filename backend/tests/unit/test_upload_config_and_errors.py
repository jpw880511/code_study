from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_file_storage
from src.config import PROJECT_ROOT, AppSettings
from src.main import create_app
from src.services.code_analysis.file_storage import FileStorage
from src.utils.file_validator import FileValidationError


def make_settings(**values: object) -> AppSettings:
    return AppSettings(_env_file=None, **values)  # type: ignore[call-arg]


# --- storage root setting ------------------------------------------------------------------


def test_the_storage_root_defaults_to_storage_uploads_in_the_repository() -> None:
    assert make_settings().upload_storage_path == PROJECT_ROOT / "storage" / "uploads"


def test_the_storage_root_can_be_set_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("UPLOAD_STORAGE_PATH", str(tmp_path))

    assert make_settings().upload_storage_path == tmp_path


def test_a_relative_storage_root_is_relative_to_the_repository_not_the_working_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_STORAGE_PATH", "./data/code")

    assert make_settings().upload_storage_path == PROJECT_ROOT / "data" / "code"


def test_the_storage_dependency_uses_the_configured_root(tmp_path: Path) -> None:
    storage = get_file_storage(make_settings(upload_storage_path=tmp_path))

    assert isinstance(storage, FileStorage)
    assert storage.root == tmp_path.resolve()


# --- FileValidationError becomes a response ------------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(make_settings())

    @app.get("/t/refuse/{code}")
    async def refuse(code: str) -> None:
        raise FileValidationError(
            code,
            "거절 사유입니다.",
            details={"extension": ".exe"},
            suggestion="이렇게 하세요.",
        )

    @app.get("/t/refuse-plain")
    async def refuse_plain() -> None:
        raise FileValidationError("file_too_large", "너무 큽니다.")

    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("file_too_large", 413),
        ("unsupported_file_type", 415),
        ("binary_file_rejected", 415),
        ("something_new", 400),
    ],
)
def test_file_validation_errors_map_to_their_status_and_keep_details_and_suggestion(
    client: TestClient, code: str, status: int
) -> None:
    response = client.get(f"/t/refuse/{code}")

    assert response.status_code == status
    assert response.json() == {
        "error": code,
        "message": "거절 사유입니다.",
        "details": {"extension": ".exe"},
        "suggestion": "이렇게 하세요.",
    }


def test_file_validation_errors_without_details_or_suggestion_omit_them(
    client: TestClient,
) -> None:
    response = client.get("/t/refuse-plain")

    assert response.status_code == 413
    assert response.json() == {"error": "file_too_large", "message": "너무 큽니다."}
