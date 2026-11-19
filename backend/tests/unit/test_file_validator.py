import os

import pytest
from src.models.code_file import SUPPORTED_EXTENSIONS
from src.models.uploaded_code import MAX_UPLOAD_SIZE_BYTES
from src.utils.file_validator import (
    FileValidationError,
    ValidatedFile,
    get_extension,
    is_binary,
    validate_binary,
    validate_extension,
    validate_file,
    validate_size,
    validate_total_size,
)

MB = 1024 * 1024


def error_of(call: object, *args: object) -> FileValidationError:
    assert callable(call)
    with pytest.raises(FileValidationError) as info:
        call(*args)
    return info.value


# ---------------------------------------------------------------- extension


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("main.py", ".py"),
        ("App.JSX", ".jsx"),
        ("archive.tar.gz", ".gz"),
        ("src/lib/util.ts", ".ts"),
        ("src\\lib\\util.ts", ".ts"),
        ("Makefile", ""),
        (".gitignore", ""),
        ("trailing.", ""),
        ("", ""),
    ],
)
def test_get_extension_is_lowercase_and_ignores_directories(filename: str, expected: str) -> None:
    assert get_extension(filename) == expected


@pytest.mark.parametrize("extension", SUPPORTED_EXTENSIONS)
def test_every_supported_extension_is_accepted(extension: str) -> None:
    assert validate_extension(f"file{extension}") == extension


def test_extension_check_is_case_insensitive_and_returns_the_normalized_value() -> None:
    assert validate_extension("Main.PY") == ".py"
    assert validate_extension("INDEX.Html") == ".html"


@pytest.mark.parametrize(
    "filename", ["app.exe", "photo.png", "data.zip", "module.pyc", "Makefile", ".env", "x.py.bak"]
)
def test_other_extensions_are_rejected(filename: str) -> None:
    error = error_of(validate_extension, filename)
    assert error.code == "unsupported_file_type"
    assert error.message.startswith("지원하지 않는 파일 형식입니다")
    assert error.details["extension"] == get_extension(filename)
    assert error.details["supported_extensions"] == list(SUPPORTED_EXTENSIONS)
    assert error.suggestion


def test_a_file_without_an_extension_is_reported_as_such() -> None:
    error = error_of(validate_extension, "Makefile")
    assert "확장자가 없는" in error.message


# --------------------------------------------------------------------- size


def test_the_limit_is_the_ten_megabytes_of_the_database_constraint() -> None:
    assert MAX_UPLOAD_SIZE_BYTES == 10 * MB


@pytest.mark.parametrize("size", [0, 1, MAX_UPLOAD_SIZE_BYTES])
def test_sizes_up_to_the_limit_are_accepted(size: int) -> None:
    validate_size(size)


def test_one_byte_over_the_limit_is_rejected_with_the_details() -> None:
    error = error_of(validate_size, MAX_UPLOAD_SIZE_BYTES + 1)
    assert error.code == "file_too_large"
    assert error.message == "파일 크기가 10MB를 초과합니다."
    assert error.details == {"max_size_mb": 10, "uploaded_size_mb": 10.0}
    assert error.suggestion == "더 작은 파일을 선택하거나 코드를 여러 태스크로 나누어 업로드하세요."


def test_the_uploaded_size_is_reported_in_megabytes() -> None:
    error = error_of(validate_size, int(15.3 * MB))
    assert error.details["uploaded_size_mb"] == 15.3


def test_a_negative_size_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="negative"):
        validate_size(-1)


def test_the_total_of_several_files_is_limited_too() -> None:
    validate_total_size([5 * MB, 5 * MB])
    validate_total_size([])
    error = error_of(validate_total_size, [5 * MB, 5 * MB, 1])
    assert error.code == "file_too_large"
    assert error.details["max_size_mb"] == 10


# ------------------------------------------------------------------- binary

SOURCE_SAMPLES = [
    b"print('hello')\n",
    "print('안녕하세요')\n".encode(),
    "print('안녕하세요')\n".encode("cp949"),
    b"line one\r\nline two\r\n\ttabbed\x0c\n",
    b"\x1b[31mcolored terminal output\x1b[0m\n",
    b"",
    b"MZ = 5\nprint(MZ)\n",
    b"GIF89 is a format name, mentioned in a comment\n",
    b"\xef\xbb\xbfconsole.log('with a UTF-8 BOM');\n",
]


@pytest.mark.parametrize("content", SOURCE_SAMPLES)
def test_source_code_is_not_binary(content: bytes) -> None:
    assert is_binary(content) is False


BINARY_SAMPLES = {
    "png": b"\x89PNG\r\n\x1a\n" + b"abc",
    "jpeg-without-nul": b"\xff\xd8\xff\xe0" + b"abc" * 10,
    "gif": b"GIF89a" + b"abc",
    "pdf": b"%PDF-1.7\n%text-looking header\n",
    "zip": b"PK\x03\x04" + b"abc",
    "gzip": b"\x1f\x8b\x08" + b"abc",
    "elf": b"\x7fELF" + b"abc",
    "java-class": b"\xca\xfe\xba\xbe" + b"abc",
    "sqlite": b"SQLite format 3\x00",
    "nul-byte-later-on": b"looks like text\n" * 10 + b"\x00" + b"more text\n",
    "utf-16": "print('hi')".encode("utf-16"),
    "random-bytes": bytes(range(256)) * 8,
}


@pytest.mark.parametrize("content", BINARY_SAMPLES.values(), ids=BINARY_SAMPLES.keys())
def test_binary_content_is_detected(content: bytes) -> None:
    assert is_binary(content) is True


def test_random_data_without_a_nul_byte_is_detected_by_its_control_characters() -> None:
    content = bytes(os.urandom(4096)).replace(b"\x00", b"\x01")
    assert is_binary(content) is True


def test_only_the_start_of_a_large_file_is_inspected() -> None:
    text = b"a = 1\n" * 100_000
    assert is_binary(text + b"\x00") is False


def test_validate_binary_raises_the_documented_error() -> None:
    validate_binary(b"print(1)\n")
    error = error_of(validate_binary, b"\x89PNG\r\n\x1a\n")
    assert error.code == "binary_file_rejected"
    assert error.message == "바이너리 파일은 업로드할 수 없습니다."
    assert "소스 코드 텍스트 파일" in error.suggestion
    assert ".py" in error.suggestion


# ---------------------------------------------------------------- validate_file


def test_a_valid_file_returns_its_normalized_facts() -> None:
    result = validate_file("Main.PY", b"print(1)\n")
    assert result == ValidatedFile(extension=".py", size_bytes=9)


def test_checks_run_cheapest_first_extension_then_size_then_content() -> None:
    assert error_of(validate_file, "x.exe", b"\x00" * (MAX_UPLOAD_SIZE_BYTES + 1)).code == (
        "unsupported_file_type"
    )
    assert error_of(validate_file, "x.py", b"a" * (MAX_UPLOAD_SIZE_BYTES + 1)).code == (
        "file_too_large"
    )
    assert error_of(validate_file, "x.py", b"\x00\x01").code == "binary_file_rejected"


def test_a_binary_file_with_a_good_extension_is_still_rejected() -> None:
    assert error_of(validate_file, "fake.py", b"\x89PNG\r\n\x1a\n").code == "binary_file_rejected"


# ------------------------------------------------------------------- the error


def test_the_error_is_an_exception_that_carries_everything_the_api_needs() -> None:
    error = FileValidationError("some_code", "무슨 일", details={"a": 1}, suggestion="해결")
    assert isinstance(error, Exception)
    assert str(error) == "무슨 일"
    assert (error.code, error.message, error.details, error.suggestion) == (
        "some_code",
        "무슨 일",
        {"a": 1},
        "해결",
    )


def test_details_and_suggestion_are_optional() -> None:
    error = FileValidationError("some_code", "무슨 일")
    assert error.details == {}
    assert error.suggestion is None
