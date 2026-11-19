from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    environment: str = "development"
    debug: bool = False
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    # Where uploaded code is stored; a relative value is relative to the repository root.
    upload_storage_path: Path = PROJECT_ROOT / "storage" / "uploads"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("upload_storage_path")
    @classmethod
    def anchor_to_project_root(cls, path: Path) -> Path:
        return PROJECT_ROOT / path  # an absolute path replaces the root

    @field_validator("allowed_origins")
    @classmethod
    def reject_wildcard(cls, origins: list[str]) -> list[str]:
        if "*" in origins:
            raise ValueError("wildcard origin is not allowed; list explicit origins instead")
        return origins
