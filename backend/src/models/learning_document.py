import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import conv

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.task import Task

# The seven chapters of a learning document (FR-026). The database insists that every one of
# these keys exists in `content`, whatever the generation status is.
CHAPTER_KEYS = (
    "chapter1",
    "chapter2",
    "chapter3",
    "chapter4",
    "chapter5",
    "chapter6",
    "chapter7",
)
GENERATION_STATUSES = ("pending", "in_progress", "completed", "failed")


def empty_content() -> dict[str, Any]:
    """Seven chapters with nothing in them: the content of a document that is not written yet.

    The check constraint rejects a document without all seven keys, so a pending, running or
    failed document needs this placeholder. The status, not the content, says what state it is in.
    A new dict every time: the chapters are mutable and must not be shared between documents.
    """
    return {key: {} for key in CHAPTER_KEYS}


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


# Mirrors the learning_documents table in alembic/versions/001_initial_schema.py: the generated
# seven-chapter explanation of a task's code (one per task) and how its generation went.
class LearningDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_documents"

    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    # Change it by assigning a new dict: an in-place edit of the nested dicts is not tracked.
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=empty_content)
    generation_status: Mapped[str | None] = mapped_column(String(20), server_default="pending")
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_error: Mapped[str | None] = mapped_column(Text)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))

    # Never lazy-loaded (async sessions cannot); load it with selectinload(LearningDocument.task).
    task: Mapped["Task"] = relationship(back_populates="learning_document", lazy="raise")

    __table_args__ = (
        # conv() keeps the database's constraint names instead of applying the naming convention.
        CheckConstraint(
            f"jsonb_typeof(content) = 'object' AND content ?& ARRAY[{_quoted(CHAPTER_KEYS)}]",
            name=conv("valid_content_structure"),
        ),
        CheckConstraint(
            f"generation_status IN ({_quoted(GENERATION_STATUSES)})",
            name=conv("learning_documents_generation_status_check"),
        ),
        UniqueConstraint("task_id", name=conv("learning_documents_task_id_key")),
        Index("idx_learning_documents_task_id", "task_id"),
        Index("idx_learning_documents_status", "generation_status"),
        Index("idx_learning_documents_celery_task", "celery_task_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<LearningDocument id={self.id} task_id={self.task_id} "
            f"status={self.generation_status}>"
        )
