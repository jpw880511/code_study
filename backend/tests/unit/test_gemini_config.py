import pytest
from pydantic import SecretStr, ValidationError
from src.services.ai.config import DEFAULT_GEMINI_MODEL, GeminiSettings

ENV_NAMES = ("GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_TIMEOUT_SECONDS")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_the_defaults_need_no_configuration() -> None:
    settings = GeminiSettings()
    assert settings.google_api_key is None
    assert settings.gemini_model == DEFAULT_GEMINI_MODEL == "gemini-3-flash-preview"
    assert settings.timeout_seconds == 120


def test_everything_can_be_set_through_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "30.5")
    settings = GeminiSettings()
    assert isinstance(settings.google_api_key, SecretStr)
    assert settings.google_api_key.get_secret_value() == "test-key-123"
    assert settings.gemini_model == "gemini-test-model"
    assert settings.timeout_seconds == 30.5


def test_the_key_never_shows_up_when_the_settings_are_printed() -> None:
    settings = GeminiSettings(google_api_key=SecretStr("super-secret-key"))
    assert "super-secret-key" not in repr(settings)
    assert "super-secret-key" not in str(settings)
    assert "super-secret-key" not in settings.model_dump_json()


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_blank_key_counts_as_no_key(monkeypatch: pytest.MonkeyPatch, blank: str) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", blank)
    assert GeminiSettings().google_api_key is None


@pytest.mark.parametrize("value", ["0", "-5", "abc"])
def test_the_timeout_must_be_a_positive_number(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", value)
    with pytest.raises(ValidationError):
        GeminiSettings()


def test_unrelated_variables_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
    assert GeminiSettings().google_api_key is None
