import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import conv

from src.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.code_file import CodeFile
    from src.models.task import Task

MAX_UPLOAD_SIZE_BYTES = 10485760  # 10 MiB (FR-014)


# Mirrors the uploaded_code table in alembic/versions/001_initial_schema.py: the metadata of the
# code a task was created from (one per task). It has no updated_at; an upload is replaced, never
# edited. The files themselves are CodeFile rows.
class UploadedCode(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "uploaded_code"

    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    detected_language: Mapped[str | None] = mapped_column(String(50))
    complexity_level: Mapped[str | None] = mapped_column(String(20))
    total_lines: Mapped[int | None] = mapped_column(Integer)
    total_files: Mapped[int | None] = mapped_column(Integer)
    upload_size_bytes: Mapped[int | None] = mapped_column(Integer)

    # Never lazy-loaded (async sessions cannot); load it with selectinload(UploadedCode.task).
    task: Mapped["Task"] = relationship(back_populates="uploaded_code", lazy="raise")
    code_files: Mapped[list["CodeFile"]] = relationship(
        back_populates="uploaded_code",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )

    __table_args__ = (
        # conv() keeps the database's constraint names instead of applying the naming convention.
        CheckConstraint(
            f"upload_size_bytes <= {MAX_UPLOAD_SIZE_BYTES}", name=conv("valid_upload_size")
        ),
        CheckConstraint(
            "complexity_level IN ('beginner', 'intermediate', 'advanced')",
            name=conv("uploaded_code_complexity_level_check"),
        ),
        UniqueConstraint("task_id", name=conv("uploaded_code_task_id_key")),
        Index("idx_uploaded_code_task_id", "task_id"),
    )

    def __repr__(self) -> str:
        return f"<UploadedCode id={self.id} task_id={self.task_id}>"
