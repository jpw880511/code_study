"""Checks an uploaded file before it is stored or analysed: type, size and "is it text?".

Pure functions with no database or filesystem access. Every refusal is a FileValidationError
whose Korean message, details and suggestion follow the project's error format (what happened,
why, what to do), so the upload service can hand it straight to the API.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from src.models.code_file import SUPPORTED_EXTENSIONS
from src.models.uploaded_code import MAX_UPLOAD_SIZE_BYTES

_MEGABYTE = 1024 * 1024
MAX_UPLOAD_SIZE_MB = MAX_UPLOAD_SIZE_BYTES // _MEGABYTE

# Only the start of a file is looked at: enough to tell text from binary, cheap for big files.
_SAMPLE_SIZE = 8192
# Control characters that appear in real text: tab, newline, form feed, carriage return, escape.
_TEXT_CONTROL_BYTES = frozenset(b"\t\n\x0c\r\x1b")
_MAX_CONTROL_RATIO = 0.05

# Signatures that are long or odd enough never to start a source file by accident.
_BINARY_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",  # JPEG
    b"GIF87a",
    b"GIF89a",
    b"%PDF-",
    b"PK\x03\x04",  # ZIP, and the formats built on it (docx, jar, ...)
    b"\x1f\x8b",  # gzip
    b"\x7fELF",
    b"\xca\xfe\xba\xbe",  # Java class file
    b"SQLite format 3\x00",
    b"Rar!\x1a\x07",
    b"7z\xbc\xaf\x27\x1c",
)


class FileValidationError(Exception):
    """An upload was refused. code is the stable machine-readable name of the reason."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion


@dataclass(frozen=True)
class ValidatedFile:
    extension: str  # lowercase, with the dot
    size_bytes: int


def get_extension(filename: str) -> str:
    """The lowercase extension with its dot, or "" when there is none.

    Directories (either separator) are ignored; a leading dot (".gitignore") is a name, not an
    extension; only the last extension counts ("a.tar.gz" -> ".gz").
    """
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    dot = name.rfind(".")
    if dot <= 0 or dot == len(name) - 1:
        return ""
    return name[dot:].lower()


def validate_extension(filename: str) -> str:
    """Return the normalized extension, or refuse a type the platform does not support."""
    extension = get_extension(filename)
    if extension in SUPPORTED_EXTENSIONS:
        return extension
    shown = extension or "확장자가 없는 파일"
    raise FileValidationError(
        "unsupported_file_type",
        f"지원하지 않는 파일 형식입니다 ({shown}).",
        details={"extension": extension, "supported_extensions": list(SUPPORTED_EXTENSIONS)},
        suggestion=f"{', '.join(SUPPORTED_EXTENSIONS)} 형식의 소스 코드 파일을 선택하세요.",
    )


def _too_large(size_bytes: int, message: str) -> FileValidationError:
    return FileValidationError(
        "file_too_large",
        message,
        details={
            "max_size_mb": MAX_UPLOAD_SIZE_MB,
            "uploaded_size_mb": round(size_bytes / _MEGABYTE, 1),
        },
        suggestion="더 작은 파일을 선택하거나 코드를 여러 태스크로 나누어 업로드하세요.",
    )


def validate_size(size_bytes: int) -> None:
    """Refuse a file above the 10MB limit (exactly 10MB is fine, like the database constraint)."""
    if size_bytes < 0:
        raise ValueError("size_bytes cannot be negative")
    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        raise _too_large(size_bytes, f"파일 크기가 {MAX_UPLOAD_SIZE_MB}MB를 초과합니다.")


def validate_total_size(sizes: Iterable[int]) -> None:
    """The limit is per task, so the files of one upload share it (FR-014)."""
    total = sum(sizes)
    if total > MAX_UPLOAD_SIZE_BYTES:
        raise _too_large(total, f"업로드한 파일의 전체 크기가 {MAX_UPLOAD_SIZE_MB}MB를 초과합니다.")


def is_binary(content: bytes) -> bool:
    """True when the start of the content looks like a binary format rather than text.

    A NUL byte, a known file signature or many control characters mean binary. High bytes alone
    do not: source files in a legacy encoding (e.g. CP949) are still text. UTF-16 is refused
    because it is full of NUL bytes.
    """
    sample = content[:_SAMPLE_SIZE]
    if not sample:
        return False
    if sample.startswith(_BINARY_SIGNATURES) or b"\x00" in sample:
        return True
    controls = sum(1 for byte in sample if byte < 0x20 and byte not in _TEXT_CONTROL_BYTES)
    return controls / len(sample) > _MAX_CONTROL_RATIO


def validate_binary(content: bytes) -> None:
    """Refuse non-text content (FR-016)."""
    if is_binary(content):
        raise FileValidationError(
            "binary_file_rejected",
            "바이너리 파일은 업로드할 수 없습니다.",
            suggestion=(
                "소스 코드 텍스트 파일만 지원합니다. "
                f"{', '.join(SUPPORTED_EXTENSIONS)} 같은 텍스트 기반 코드 파일을 선택하세요."
            ),
        )


def validate_file(filename: str, content: bytes) -> ValidatedFile:
    """All per-file checks, cheapest first: extension, size, then the content itself."""
    extension = validate_extension(filename)
    validate_size(len(content))
    validate_binary(content)
    return ValidatedFile(extension=extension, size_bytes=len(content))
