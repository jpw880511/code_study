"""Where uploaded code lives on disk: {root}/{user_id}/{task_id}/{uuid4}{extension}.

Only values the server made (UUIDs and an extension from the supported list) ever become part
of a disk path; what the user typed (file names, folder paths) lives in the database only. On
top of that, every path read back is resolved and must stay inside the storage root, so a
corrupted database row or a link planted in the folder cannot lead the server to other files.
"""

import logging
import shutil
import uuid
from pathlib import Path

from src.models.code_file import SUPPORTED_EXTENSIONS
from src.services.task_errors import CodeFileMissingError

logger = logging.getLogger(__name__)


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def save(self, user_id: uuid.UUID, task_id: uuid.UUID, extension: str, content: bytes) -> str:
        """Write one file and return its path relative to the root ("/"-separated)."""
        if extension not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"unsupported extension: {extension!r}")
        relative = f"{user_id}/{task_id}/{uuid.uuid4()}{extension}"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return relative

    def read(self, storage_path: str) -> bytes:
        """The bytes at a stored path, or CodeFileMissingError if it is gone or not allowed."""
        path = self._resolve(storage_path)
        try:
            return path.read_bytes()
        except OSError as exc:  # missing file, or a directory
            raise CodeFileMissingError() from exc

    def discard_task(self, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
        """Remove everything stored for a task, and the user's folder when it is left empty."""
        user_dir = self.root / str(user_id)
        shutil.rmtree(user_dir / str(task_id), ignore_errors=True)
        try:
            user_dir.rmdir()
        except OSError:  # missing, or other tasks of the user are still in it
            pass

    def _resolve(self, storage_path: str) -> Path:
        segments = storage_path.split("/")
        unsafe = (
            not storage_path
            or "\\" in storage_path
            or "\x00" in storage_path
            or ":" in storage_path
            or any(segment in ("", ".", "..") for segment in segments)
        )
        resolved = None if unsafe else (self.root / storage_path).resolve()
        if resolved is None or not resolved.is_relative_to(self.root):
            logger.warning("Refused a stored path outside the storage root: %r", storage_path)
            raise CodeFileMissingError()
        return resolved
