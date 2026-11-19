"""Creates a task together with its uploaded code (file, folder or pasted text) and reads it back.

Order of checks (contract phase5-tasks-upload-api.md): project ownership, upload method, title,
description, then per method: paths, exclusions (FR-017), file count, each file (extension, size,
binary) and finally the total size. Nothing is written until every check has passed; the writes
themselves are undone (database savepoint and files on disk) if any of them fails.
"""

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CodeFile, Task, UploadedCode
from src.models.uploaded_code import MAX_UPLOAD_SIZE_BYTES
from src.services.code_analysis.complexity_analyzer import (
    NON_CODE_LANGUAGES,
    ComplexityReport,
    FileMetrics,
    assess,
    measure_source,
)
from src.services.code_analysis.file_storage import FileStorage
from src.services.code_analysis.language_detector import UNKNOWN_LANGUAGE, detect_language
from src.services.code_analysis.upload_errors import (
    EmptyCodeError,
    InvalidFilePathError,
    InvalidUploadMethodError,
    LanguageRequiredError,
    NoFilesError,
    TooManyFilesError,
    UnsupportedLanguageError,
)
from src.services.document.document_queue_service import DocumentQueueService
from src.services.project_service import ProjectService
from src.services.task_errors import CodeNotFoundError
from src.services.task_service import (
    TaskService,
    normalize_task_description,
    normalize_task_title,
)
from src.utils.file_validator import (
    validate_extension,
    validate_file,
    validate_total_size,
)

UPLOAD_METHODS = ("file", "folder", "paste")
MAX_FILES = 20
MAX_NAME_LENGTH = 255  # code_files.file_name is VARCHAR(255)
LARGE_CODE_LINES = 500
LARGE_CODE_WARNING = (
    "큰 코드 파일이 감지되었습니다. 500줄을 넘는 코드는 문서 생성에 3~5분이 걸릴 수 있습니다. "
    "다른 화면으로 이동했다가 준비되면 다시 돌아와도 됩니다."
)
EXCLUDED_DIRECTORIES = frozenset({".git", "node_modules", "__pycache__"})
EXCLUDED_FILES = frozenset({".DS_Store"})
PASTE_FILE_STEM = "pasted_code"
# The languages of the paste dropdown (FR-013) and the extension of the file made from them.
PASTE_EXTENSIONS = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "java": ".java",
    "c": ".c",
    "cpp": ".cpp",
    "html": ".html",
    "css": ".css",
    "markdown": ".md",
    "text": ".txt",
}
MIME_TYPES = {
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".jsx": "text/javascript",
    ".ts": "text/typescript",
    ".tsx": "text/typescript",
    ".html": "text/html",
    ".css": "text/css",
    ".java": "text/x-java-source",
    ".cpp": "text/x-c++src",
    ".c": "text/x-csrc",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class AsyncReadable(Protocol):
    """What the service needs of an uploaded part (Starlette's UploadFile has it)."""

    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True)
class IncomingFile:
    name: str
    source: AsyncReadable


@dataclass(frozen=True)
class UploadWarning:
    code: str
    message: str


@dataclass(frozen=True)
class UploadResult:
    """The new task with its upload and files loaded."""

    task: Task
    excluded_paths: list[str]
    warnings: list[UploadWarning]
    # The id the document's job is to be sent under once the request has committed.
    document_job_id: str | None = None


@dataclass(frozen=True)
class StoredCode:
    file: CodeFile
    language: str
    content: str


@dataclass(frozen=True)
class FileLanguage:
    language: str
    lines: int


@dataclass(frozen=True)
class _PreparedFile:
    """A file that passed every check: what to store and what was measured."""

    name: str
    path: str | None
    extension: str
    content: bytes
    language: str
    metrics: FileMetrics


def normalize_relative_path(path: str) -> str:
    """A "/"-separated relative path as the browser sent it, or InvalidFilePathError.

    The path only ever goes to the database, never to the disk, but it is shown to the learner
    and sent back to the browser, so it is held to the same standard: no absolute paths, no
    "." or ".." or empty segments, no backslashes, drive letters or control characters.
    """
    segments = path.split("/")
    if (
        not path
        or any(segment in ("", ".", "..") for segment in segments)
        or any(len(segment) > MAX_NAME_LENGTH for segment in segments)
        or any(ord(char) < 0x20 or char in "\\:\x7f" for char in path)
    ):
        raise InvalidFilePathError()
    return path


def is_excluded(path: str) -> bool:
    """Build and system files the server leaves out of a folder upload (FR-017)."""
    *directories, name = path.split("/")
    return name in EXCLUDED_FILES or any(d in EXCLUDED_DIRECTORIES for d in directories)


def choose_primary_language(files: Sequence[FileLanguage]) -> str:
    """The language with the most lines among code files; the first uploaded wins a tie.

    Without any code file (only documentation) the most common of all files decides, and
    "unknown" counts only when there is nothing else.
    """
    code = [f for f in files if f.language not in NON_CODE_LANGUAGES]
    known = [f for f in files if f.language != UNKNOWN_LANGUAGE]
    for candidates in (code, known):
        if candidates:
            totals: dict[str, int] = defaultdict(int)
            for f in candidates:
                totals[f.language] += f.lines
            return max(totals, key=lambda language: totals[language])  # first max wins
    return UNKNOWN_LANGUAGE


def _base_name(filename: str) -> str:
    """The file name of a single-file upload: browsers send the bare name, but be safe."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not name or name in (".", "..") or len(name) > MAX_NAME_LENGTH:
        raise InvalidFilePathError()
    if any(ord(char) < 0x20 or char == "\x7f" for char in name):
        raise InvalidFilePathError()
    return name


def _decode(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _measured(
    name: str, path: str | None, extension: str, content: bytes, language: str
) -> _PreparedFile:
    metrics = measure_source(_decode(content), language)
    return _PreparedFile(name, path, extension, content, language, metrics)


class CodeUploadService:
    """Task creation with code, and reading the code back. It never commits."""

    def __init__(self, session: AsyncSession, storage: FileStorage) -> None:
        self.session = session
        self.storage = storage

    async def create_task(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        *,
        title: str | None,
        description: str | None,
        upload_method: str | None,
        files: Sequence[IncomingFile] = (),
        paths: Sequence[str] = (),
        code: str | None = None,
        language: str | None = None,
    ) -> UploadResult:
        await ProjectService(self.session).get(user_id, project_id)
        if upload_method not in UPLOAD_METHODS:
            raise InvalidUploadMethodError()
        normalize_task_title(title)
        normalize_task_description(description)

        excluded: list[str] = []
        if upload_method == "paste":
            prepared = [self._prepare_paste(code, language)]
        else:
            prepared, excluded = await self._prepare_files(upload_method, files, paths)

        task_id, report = await self._store(
            user_id, project_id, title, description, upload_method, prepared
        )
        # The document row is part of this transaction: it commits with the task or not at all.
        document = await DocumentQueueService(self.session).register(task_id)
        task = await TaskService(self.session).get(user_id, task_id)
        warnings = []
        if report.code_lines > LARGE_CODE_LINES:
            warnings.append(UploadWarning("large_code", LARGE_CODE_WARNING))
        return UploadResult(
            task=task,
            excluded_paths=excluded,
            warnings=warnings,
            document_job_id=document.celery_task_id,
        )

    async def read_code(self, user_id: uuid.UUID, task_id: uuid.UUID) -> list[StoredCode]:
        """Every file of a task with its content, ordered by path (or name)."""
        task = await TaskService(self.session).get(user_id, task_id)  # ownership, trash rules
        upload = task.uploaded_code
        if upload is None:
            raise CodeNotFoundError()
        result = []
        for code_file in sort_files(upload.code_files):
            content = _decode(await asyncio.to_thread(self.storage.read, code_file.storage_path))
            name = code_file.file_path or code_file.file_name
            result.append(StoredCode(code_file, detect_language(name, content), content))
        return result

    # --- preparing (no database writes, no disk writes) ------------------------------------

    def _prepare_paste(self, code: str | None, language: str | None) -> _PreparedFile:
        if language is None or not language.strip():
            raise LanguageRequiredError()
        choice = language.strip().lower()
        extension = PASTE_EXTENSIONS.get(choice)
        if extension is None:
            raise UnsupportedLanguageError()
        if code is None or not code.strip():
            raise EmptyCodeError()
        name = f"{PASTE_FILE_STEM}{extension}"
        content = code.encode("utf-8")
        validate_file(name, content)
        # The dropdown values are already the canonical names of normalize_language().
        return _measured(name, None, extension, content, choice)

    async def _prepare_files(
        self, method: str, files: Sequence[IncomingFile], paths: Sequence[str]
    ) -> tuple[list[_PreparedFile], list[str]]:
        entries: list[tuple[IncomingFile, str, str | None]] = []  # file, name, relative path
        excluded: list[str] = []
        if method == "folder":
            if len(paths) != len(files):
                raise InvalidFilePathError()
            for incoming, raw_path in zip(files, paths, strict=True):
                path = normalize_relative_path(raw_path)
                if is_excluded(path):
                    excluded.append(path)
                else:
                    entries.append((incoming, path.rsplit("/", 1)[-1], path))
        else:
            entries = [(f, _base_name(f.name), None) for f in files]
        if not entries:
            raise NoFilesError()
        if len(entries) > MAX_FILES:
            raise TooManyFilesError()

        prepared: list[_PreparedFile] = []
        total = 0
        for upload, name, rel_path in entries:
            extension = validate_extension(name)
            # One byte more than the limit is enough to know the file is too big.
            content = await upload.source.read(MAX_UPLOAD_SIZE_BYTES + 1)
            validate_file(name, content)
            language = detect_language(rel_path or name, _decode(content))
            prepared.append(_measured(name, rel_path, extension, content, language))
            total += len(content)
            if total > MAX_UPLOAD_SIZE_BYTES:
                break  # no need to read more: the total check below refuses the upload
        validate_total_size(len(f.content) for f in prepared)
        return prepared, excluded

    # --- storing ---------------------------------------------------------------------------

    async def _store(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        title: str | None,
        description: str | None,
        upload_method: str,
        prepared: list[_PreparedFile],
    ) -> tuple[uuid.UUID, ComplexityReport]:
        """Task, upload row, file rows and files on disk, all or nothing."""
        report = assess(f.metrics for f in prepared)
        task_id: uuid.UUID | None = None
        try:
            async with self.session.begin_nested():
                task = await TaskService(self.session).create(
                    user_id, project_id, title, description, upload_method
                )
                task_id = task.id
                code_files = []
                for item in prepared:
                    storage_path = await asyncio.to_thread(
                        self.storage.save, user_id, task.id, item.extension, item.content
                    )
                    code_files.append(
                        CodeFile(
                            file_name=item.name,
                            file_path=item.path,
                            file_extension=item.extension,
                            file_size_bytes=len(item.content),
                            storage_path=storage_path,
                            mime_type=MIME_TYPES[item.extension],
                        )
                    )
                upload = UploadedCode(
                    task_id=task.id,
                    detected_language=choose_primary_language(
                        [FileLanguage(f.language, f.metrics.lines) for f in prepared]
                    ),
                    complexity_level=report.level,
                    total_lines=report.total_lines,
                    total_files=len(prepared),
                    upload_size_bytes=sum(len(f.content) for f in prepared),
                )
                upload.code_files = code_files
                self.session.add(upload)
                await self.session.flush()
        except BaseException:
            if task_id is not None:
                await asyncio.to_thread(self.storage.discard_task, user_id, task_id)
            raise
        return task_id, report


def sort_files(files: Sequence[CodeFile]) -> list[CodeFile]:
    """Contract order: by path (or the name when there is no path), ascending."""
    return sorted(files, key=lambda f: f.file_path or f.file_name)
