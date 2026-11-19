"""Names the programming language of an uploaded file (FR-020).

The name comes from the file name through Pygments, then from a shebang line. The content is
deliberately not guessed: Pygments' guess_lexer labels short snippets wrongly (a JavaScript
arrow function as GDScript, Markdown as T-SQL), and a wrong name would be stored and shown to
the learner, so "unknown" is the better answer. Pasted code has no file name; there the user
picks the language from a dropdown (FR-013) and normalize_language() turns that choice into the
same names this module returns.
"""

from pygments.lexers import find_lexer_class_by_name, find_lexer_class_for_filename
from pygments.util import ClassNotFound

UNKNOWN_LANGUAGE = "unknown"
TEXT_LANGUAGE = "text"

# Pygments names JSX and TSX after the dialect; for the learner they are JavaScript and TypeScript.
_CANONICAL_NAMES = {"jsx": "javascript", "tsx": "typescript"}
# Names a user may type that Pygments does not know.
_CHOICE_ALIASES = {"txt": TEXT_LANGUAGE}

# Interpreter (without version digits) -> language, for "#!/usr/bin/env python3" style lines.
_SHEBANG_LANGUAGES = {
    "python": "python",
    "node": "javascript",
    "nodejs": "javascript",
    "bash": "bash",
    "sh": "bash",
    "zsh": "bash",
    "dash": "bash",
    "ksh": "bash",
    "ruby": "ruby",
    "perl": "perl",
    "php": "php",
}
_SHEBANG_SCAN_LENGTH = 256


def _canonical(lexer_class: type) -> str:
    alias: str = lexer_class.aliases[0]  # type: ignore[attr-defined]
    return _CANONICAL_NAMES.get(alias, alias)


def _lexer_class_for_filename(filename: str) -> type | None:
    """Pygments matches file name patterns case-sensitively, so retry in lowercase."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not name:
        return None
    found: type | None = find_lexer_class_for_filename(name) or find_lexer_class_for_filename(
        name.lower()
    )
    return found


def _language_from_shebang(content: str) -> str | None:
    first_line = content[:_SHEBANG_SCAN_LENGTH].lstrip("﻿").split("\n", 1)[0].strip()
    if not first_line.startswith("#!"):
        return None
    tokens = first_line[2:].split()
    if not tokens:
        return None
    program = tokens[0].rsplit("/", 1)[-1]
    if program == "env":
        # "env -S python3 -u" and "env VAR=1 python3": skip options and assignments.
        candidates = [t for t in tokens[1:] if not t.startswith("-") and "=" not in t]
        if not candidates:
            return None
        program = candidates[0].rsplit("/", 1)[-1]
    return _SHEBANG_LANGUAGES.get(program.rstrip("0123456789."))


def detect_language(filename: str, content: str = "") -> str:
    """The language of a file, or UNKNOWN_LANGUAGE; a .txt file without a shebang is "text".

    The file name decides first (a known extension is never overruled by the content), then a
    shebang on the first line for scripts without an extension.
    """
    lexer_class = _lexer_class_for_filename(filename)
    language = _canonical(lexer_class) if lexer_class is not None else None
    if language is not None and language != TEXT_LANGUAGE:
        return language
    from_shebang = _language_from_shebang(content)
    if from_shebang is not None:
        return from_shebang
    return language or UNKNOWN_LANGUAGE


def normalize_language(name: str) -> str | None:
    """The canonical name of a language a user typed or picked, or None if it is not known."""
    key = name.strip().lower()
    if not key:
        return None
    if key in _CHOICE_ALIASES:
        return _CHOICE_ALIASES[key]
    try:
        return _canonical(find_lexer_class_by_name(key))
    except ClassNotFound:
        return None
