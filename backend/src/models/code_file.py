import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import conv

from src.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.uploaded_code import UploadedCode

# The file types a learner may upload (FR-015). The database repeats them in a CHECK constraint;
# the upload validator (T064) should use this tuple so the two cannot drift apart.
SUPPORTED_EXTENSIONS = (
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".css",
    ".java",
    ".cpp",
    ".c",
    ".txt",
    ".md",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


# Mirrors the code_files table in alembic/versions/001_initial_schema.py: one file of an upload.
# The content lives on disk at storage_path; this row only describes it.
class CodeFile(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "code_files"

    uploaded_code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("uploaded_code.id", ondelete="CASCADE")
    )
    file_name: Mapped[str] = mapped_column(String(255))
    # Relative path inside an uploaded folder.
    file_path: Mapped[str | None] = mapped_column(Text)
    file_extension: Mapped[str | None] = mapped_column(String(20))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(100))

    # Never lazy-loaded (async sessions cannot); load it with selectinload(CodeFile.uploaded_code).
    uploaded_code: Mapped["UploadedCode"] = relationship(back_populates="code_files", lazy="raise")

    __table_args__ = (
        # conv() keeps the database's constraint name instead of applying the naming convention.
        CheckConstraint(
            f"file_extension IN ({_quoted(SUPPORTED_EXTENSIONS)})",
            name=conv("supported_extension"),
        ),
        Index("idx_code_files_uploaded_code_id", "uploaded_code_id"),
    )

    def __repr__(self) -> str:
        return f"<CodeFile id={self.id} uploaded_code_id={self.uploaded_code_id}>"
