import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class Credentials(BaseModel):
    """Email format and password rules are checked by the service, not here."""

    email: str
    password: str


class UserResponse(BaseModel):
    """What the API says about a user. Never add password_hash or other internal columns."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    skill_level: str | None


class ProjectCreate(BaseModel):
    """Length and blank-title rules are checked by the service, not here."""

    title: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    """A partial update: only the fields present in the JSON body change.

    `title: null` is a field that is present (and invalid); an omitted title is left alone.
    """

    title: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("title 또는 description 중 하나 이상을 보내야 합니다.")
        return self


class ProjectResponse(BaseModel):
    """What the API says about a project. Never add user_id or the deletion fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
