import pytest
from src.services.code_analysis.code_upload_service import (
    LARGE_CODE_LINES,
    PASTE_EXTENSIONS,
    FileLanguage,
    choose_primary_language,
    is_excluded,
    normalize_relative_path,
)
from src.services.code_analysis.language_detector import normalize_language
from src.services.code_analysis.upload_errors import InvalidFilePathError

# --- path normalisation --------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["a.py", "my-app/src/App.jsx", "한글/폴더/파일.py", "a b/c d.js", "x/.hidden.py"]
)
def test_a_relative_slash_path_is_kept_as_it_is(path: str) -> None:
    assert normalize_relative_path(path) == path


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/etc/passwd",
        "/a.py",
        "../a.py",
        "a/../b.py",
        "a/..",
        "a/./b.py",
        "./a.py",
        "a//b.py",
        "a/",
        "a\\b.py",
        "C:/a.py",
        "C:a.py",
        "a/b:c.py",
        "a\x00.py",
        "a\n.py",
        "a\t/b.py",
        "x" * 256 + ".py",
        "dir/" + "x" * 256,
    ],
)
def test_an_unsafe_path_is_refused(path: str) -> None:
    with pytest.raises(InvalidFilePathError) as raised:
        normalize_relative_path(path)
    assert raised.value.message == "파일 경로가 올바르지 않습니다."


# --- exclusion (FR-017) --------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ".git/config",
        "app/.git/HEAD",
        "node_modules/a/index.js",
        "app/node_modules/x.js",
        "__pycache__/a.pyc",
        "pkg/__pycache__/m.py",
        ".DS_Store",
        "src/.DS_Store",
    ],
)
def test_build_and_system_paths_are_excluded(path: str) -> None:
    assert is_excluded(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/App.jsx",
        "git/config.py",
        ".gitignore",
        "node_modules.py",
        "my.git/a.py",
        "src/__pycache__.py",
        # a directory named like the excluded file is not that file
        "a/.DS_Store/b.py",
    ],
)
def test_other_paths_are_kept(path: str) -> None:
    assert not is_excluded(path)


# --- primary language ----------------------------------------------------------------------


def lang(language: str, lines: int) -> FileLanguage:
    return FileLanguage(language=language, lines=lines)


def test_the_code_language_with_the_most_lines_wins() -> None:
    files = [lang("python", 10), lang("javascript", 30), lang("python", 25)]
    assert choose_primary_language(files) == "python"


def test_documentation_does_not_outweigh_code() -> None:
    files = [lang("markdown", 500), lang("text", 400), lang("css", 3)]
    assert choose_primary_language(files) == "css"


def test_without_code_the_most_common_overall_wins() -> None:
    assert choose_primary_language([lang("text", 5), lang("markdown", 9)]) == "markdown"


def test_a_tie_goes_to_the_language_uploaded_first() -> None:
    assert choose_primary_language([lang("java", 5), lang("python", 5)]) == "java"
    assert choose_primary_language([lang("python", 5), lang("java", 5)]) == "python"
    assert choose_primary_language([lang("text", 2), lang("markdown", 2)]) == "text"


def test_all_unknown_is_unknown() -> None:
    assert choose_primary_language([lang("unknown", 4), lang("unknown", 1)]) == "unknown"


def test_unknown_only_wins_when_nothing_else_exists() -> None:
    assert choose_primary_language([lang("unknown", 50), lang("text", 1)]) == "text"


def test_no_files_is_unknown() -> None:
    assert choose_primary_language([]) == "unknown"


# --- constants -----------------------------------------------------------------------------


def test_paste_extensions_follow_the_contract() -> None:
    assert PASTE_EXTENSIONS == {
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


def test_paste_languages_are_the_canonical_names_of_the_language_detector() -> None:
    for choice in PASTE_EXTENSIONS:
        assert normalize_language(choice) == choice


def test_large_code_threshold_is_500_lines() -> None:
    assert LARGE_CODE_LINES == 500
