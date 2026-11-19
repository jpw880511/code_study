from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import conv

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.project import Project
    from src.models.refresh_token import RefreshToken

# Mirrors the users table in alembic/versions/001_initial_schema.py.
EMAIL_PATTERN = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    skill_level: Mapped[str | None] = mapped_column(String(50), server_default="Complete Beginner")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Never lazy-loaded (async sessions cannot); load it with selectinload(User.refresh_tokens).
    # The database deletes the tokens (ON DELETE CASCADE), so the ORM does not load them first.
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    projects: Mapped[list["Project"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    __table_args__ = (
        # conv() keeps the database's constraint name instead of applying the naming convention.
        CheckConstraint(f"email ~* '{EMAIL_PATTERN}'", name=conv("valid_email")),
        Index("idx_users_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
