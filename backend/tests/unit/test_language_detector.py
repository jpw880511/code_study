import pytest
from src.models.code_file import SUPPORTED_EXTENSIONS
from src.services.code_analysis.language_detector import (
    TEXT_LANGUAGE,
    UNKNOWN_LANGUAGE,
    detect_language,
    normalize_language,
)

# The language stored in uploaded_code.detected_language for each type the platform accepts.
EXPECTED_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".txt": "text",
    ".md": "markdown",
}


def test_the_expectations_cover_every_supported_extension() -> None:
    assert set(EXPECTED_BY_EXTENSION) == set(SUPPORTED_EXTENSIONS)


@pytest.mark.parametrize(("extension", "language"), EXPECTED_BY_EXTENSION.items())
def test_every_supported_extension_has_a_language(extension: str, language: str) -> None:
    assert detect_language(f"file{extension}") == language


def test_the_names_fit_the_database_column() -> None:
    assert all(len(name) <= 50 for name in EXPECTED_BY_EXTENSION.values())
    assert len(UNKNOWN_LANGUAGE) <= 50
    assert len(TEXT_LANGUAGE) <= 50


@pytest.mark.parametrize("filename", ["App.JSX", "MAIN.PY", "Index.Html", "STYLE.CSS"])
def test_the_extension_is_case_insensitive(filename: str) -> None:
    assert (
        detect_language(filename) == EXPECTED_BY_EXTENSION[f".{filename.rsplit('.', 1)[1].lower()}"]
    )


@pytest.mark.parametrize("filename", ["src/lib/util.py", "src\\lib\\util.py", "a/b/c/util.py"])
def test_directories_are_ignored(filename: str) -> None:
    assert detect_language(filename) == "python"


@pytest.mark.parametrize(
    ("filename", "language"),
    [("legacy.h", "c"), ("legacy.cc", "cpp"), ("legacy.hpp", "cpp"), ("data.json", "json")],
)
def test_other_known_file_types_are_named_by_pygments(filename: str, language: str) -> None:
    assert detect_language(filename) == language


def test_well_known_file_names_without_an_extension_are_recognised() -> None:
    assert detect_language("Makefile") == "make"


@pytest.mark.parametrize("filename", ["", ".gitignore", "data.unknownext", "README", "x.py.bak"])
def test_unrecognised_names_are_unknown(filename: str) -> None:
    assert detect_language(filename) == UNKNOWN_LANGUAGE


# ------------------------------------------------------------------ shebang


@pytest.mark.parametrize(
    ("first_line", "language"),
    [
        ("#!/usr/bin/env python3", "python"),
        ("#!/usr/bin/python3.11", "python"),
        ("#!/usr/bin/python", "python"),
        ("#!/usr/bin/env -S python3 -u", "python"),
        ("#!/usr/bin/env PYTHONUNBUFFERED=1 python3", "python"),
        ("#!/usr/bin/env node", "javascript"),
        ("#!/usr/bin/nodejs", "javascript"),
        ("#!/bin/bash", "bash"),
        ("#!/bin/sh", "bash"),
        ("#!/usr/bin/env zsh", "bash"),
        ("#! /usr/bin/ruby", "ruby"),
        ("#!/usr/bin/perl -w", "perl"),
        ("#!/usr/bin/env php", "php"),
        ("#!/bin/bash\r", "bash"),
        ("﻿#!/usr/bin/env python3", "python"),
    ],
)
def test_a_shebang_names_a_file_without_an_extension(first_line: str, language: str) -> None:
    assert detect_language("run", f"{first_line}\nprint('hi')\n") == language


@pytest.mark.parametrize(
    "first_line",
    ["#!/usr/bin/unknown-tool", "#!/usr/bin/env", "#!", "# python", "print('#!/usr/bin/env node')"],
)
def test_a_missing_or_unknown_shebang_changes_nothing(first_line: str) -> None:
    assert detect_language("run", f"{first_line}\n") == UNKNOWN_LANGUAGE


def test_the_shebang_is_only_read_from_the_first_line() -> None:
    assert detect_language("run", "echo hi\n#!/usr/bin/env python3\n") == UNKNOWN_LANGUAGE


def test_a_known_extension_beats_the_shebang() -> None:
    assert detect_language("app.js", "#!/usr/bin/env python3\nprint(1)\n") == "javascript"


def test_a_shebang_beats_the_plain_text_guess_of_a_txt_file() -> None:
    assert detect_language("notes.txt", "#!/usr/bin/env python3\nprint(1)\n") == "python"


# -------------------------------------------------- content is not guessed

JS_ARROW = "const add = (a, b) => a + b;\nconsole.log(add(1, 2));\n"
PYTHON_IMPORT = "import os\n\ndef main():\n    print(os.getcwd())\n"


def test_content_alone_never_names_a_language() -> None:
    # Pygments' guess_lexer labels this JavaScript snippet GDScript, so a wrong name would be
    # stored and shown to the learner. "unknown" is the honest answer; paste uploads send the
    # language the user picked instead (see normalize_language).
    assert detect_language("snippet.unknownext", JS_ARROW) == UNKNOWN_LANGUAGE
    assert detect_language("", PYTHON_IMPORT) == UNKNOWN_LANGUAGE


def test_a_txt_file_stays_text_whatever_it_contains() -> None:
    assert detect_language("snippet.txt", JS_ARROW) == TEXT_LANGUAGE
    assert detect_language("snippet.txt", PYTHON_IMPORT) == TEXT_LANGUAGE


def test_the_content_never_overrides_the_extension() -> None:
    assert detect_language("page.html", PYTHON_IMPORT) == "html"
    assert detect_language("legacy.h", "class A { public: int x; };") == "c"


# ------------------------------------------------------ normalize_language


@pytest.mark.parametrize(
    ("chosen", "language"),
    [
        ("python", "python"),
        ("Python", "python"),
        ("  JS  ", "javascript"),
        ("javascript", "javascript"),
        ("jsx", "javascript"),
        ("ts", "typescript"),
        ("TSX", "typescript"),
        ("c++", "cpp"),
        ("cpp", "cpp"),
        ("c", "c"),
        ("html", "html"),
        ("css", "css"),
        ("java", "java"),
        ("md", "markdown"),
        ("markdown", "markdown"),
        ("txt", "text"),
        ("text", "text"),
        ("c#", "csharp"),
        ("sh", "bash"),
    ],
)
def test_the_language_a_user_picks_gets_the_canonical_name(chosen: str, language: str) -> None:
    assert normalize_language(chosen) == language


@pytest.mark.parametrize("chosen", ["", "   ", "nonsense", "python 3", "not a language at all"])
def test_a_language_nobody_knows_is_none(chosen: str) -> None:
    assert normalize_language(chosen) is None


def test_every_detected_name_is_also_a_valid_choice() -> None:
    # A name this module hands out must survive being sent back through normalize_language.
    for language in EXPECTED_BY_EXTENSION.values():
        assert normalize_language(language) == language
