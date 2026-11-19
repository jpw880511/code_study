import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import conv

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.task import Task
    from src.models.user import User


# Mirrors the projects table in alembic/versions/001_initial_schema.py. A project is "trashed"
# (soft deleted) instead of removed; last_activity_at is the last TASK activity.
class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    deletion_status: Mapped[str | None] = mapped_column(String(20), server_default="active")
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_deletion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Never lazy-loaded (async sessions cannot); load it with selectinload(Project.user).
    user: Mapped["User"] = relationship(back_populates="projects", lazy="raise")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    __table_args__ = (
        # conv() keeps the database's constraint names instead of applying the naming convention.
        CheckConstraint("char_length(title) >= 1", name=conv("title_min_length")),
        CheckConstraint(
            "deletion_status IN ('active', 'trashed')", name=conv("projects_deletion_status_check")
        ),
        Index("idx_projects_user_id", "user_id"),
        Index("idx_projects_deletion_status", "deletion_status"),
        Index(
            "idx_projects_user_active",
            "user_id",
            "deletion_status",
            postgresql_where=text("deletion_status = 'active'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} user_id={self.user_id}>"
