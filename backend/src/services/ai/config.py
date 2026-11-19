from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config import PROJECT_ROOT

DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"


class GeminiSettings(BaseSettings):
    """Where the AI client finds its key, model and time limit (env vars or the repo's .env).

    Having no key is not an error here: the application, the tests and every endpoint that does
    not talk to the AI start without one. The client refuses at the moment of the first call.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", extra="ignore", populate_by_name=True
    )

    google_api_key: SecretStr | None = Field(default=None, validation_alias="GOOGLE_API_KEY")
    gemini_model: str = Field(default=DEFAULT_GEMINI_MODEL, validation_alias="GEMINI_MODEL")
    # Document generation may take minutes (FR-083: 3 minutes for 500 lines); Q&A passes a much
    # shorter limit per call (FR-087: 10 seconds).
    timeout_seconds: float = Field(default=120, gt=0, validation_alias="GEMINI_TIMEOUT_SECONDS")

    @field_validator("google_api_key", mode="before")
    @classmethod
    def blank_key_is_no_key(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
