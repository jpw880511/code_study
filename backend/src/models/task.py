import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import conv

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.learning_document import LearningDocument
    from src.models.project import Project
    from src.models.uploaded_code import UploadedCode


# Mirrors the tasks table in alembic/versions/001_initial_schema.py. task_number is assigned by
# TaskService (sequential per project, immutable); the database only keeps it unique.
class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    task_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    upload_method: Mapped[str | None] = mapped_column(String(20))
    deletion_status: Mapped[str | None] = mapped_column(String(20), server_default="active")
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_deletion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Never lazy-loaded (async sessions cannot); load it with selectinload(Task.project).
    project: Mapped["Project"] = relationship(back_populates="tasks", lazy="raise")
    uploaded_code: Mapped["UploadedCode | None"] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
        lazy="raise",
    )
    learning_document: Mapped["LearningDocument | None"] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
        lazy="raise",
    )

    __table_args__ = (
        # conv() keeps the database's constraint names instead of applying the naming convention.
        CheckConstraint("char_length(title) >= 5", name=conv("title_min_length")),
        CheckConstraint("char_length(description) <= 500", name=conv("description_max_length")),
        CheckConstraint(
            "upload_method IN ('file', 'folder', 'paste')", name=conv("tasks_upload_method_check")
        ),
        CheckConstraint(
            "deletion_status IN ('active', 'trashed')", name=conv("tasks_deletion_status_check")
        ),
        UniqueConstraint("project_id", "task_number", name=conv("unique_task_number_per_project")),
        Index("idx_tasks_project_id", "project_id"),
        Index("idx_tasks_deletion_status", "deletion_status"),
        Index(
            "idx_tasks_project_active",
            "project_id",
            "deletion_status",
            postgresql_where=text("deletion_status = 'active'"),
        ),
        Index("idx_tasks_number_order", "project_id", "task_number"),
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} project_id={self.project_id} number={self.task_number}>"
