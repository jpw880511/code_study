from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_prefix="DB_", extra="ignore"
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)
    pool_timeout: int = Field(default=30, ge=1)
    pool_recycle: int = Field(default=1800, ge=-1)
    pool_pre_ping: bool = True
    echo: bool = False

    @property
    def engine_options(self) -> dict[str, Any]:
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
            "echo": self.echo,
        }


def get_database_settings() -> DatabaseSettings:
    try:
        return DatabaseSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        raise RuntimeError(
            "DATABASE_URL is not set (define it in .env or the environment)"
        ) from exc
