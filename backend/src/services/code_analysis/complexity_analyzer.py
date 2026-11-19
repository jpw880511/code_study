"""Rates how demanding an upload's code is: beginner, intermediate or advanced (FR-021).

Three measurements decide, as the research notes say: lines of code, number of functions and
how deeply blocks are nested. The level is the most demanding of the three, so a short but deeply
nested program is not "beginner". Source text is read with Pygments tokens (braces) and Python's
tokenizer (indentation), never with plain text searches, so braces, `def` and `function` inside
strings and comments are not counted.

The thresholds below are a product decision rather than something the specification fixes;
change them here and the tests will show which boundaries moved.
"""

import io
import tokenize
from collections.abc import Iterable
from dataclasses import dataclass

from pygments.lexers import get_lexer_by_name
from pygments.token import Keyword, Name, Punctuation

BEGINNER = "beginner"
INTERMEDIATE = "intermediate"
ADVANCED = "advanced"
LEVELS = (BEGINNER, INTERMEDIATE, ADVANCED)

# Beginner needs every metric at or below its ceiling ...
BEGINNER_MAX_LINES = 100
BEGINNER_MAX_FUNCTIONS = 5
BEGINNER_MAX_DEPTH = 4  # a class, a method, a loop and an if
# ... and one metric above its ceiling is enough for advanced. The line threshold is below the
# 500-line "typical task" of FR-025.
ADVANCED_ABOVE_LINES = 300
ADVANCED_ABOVE_FUNCTIONS = 15
ADVANCED_ABOVE_DEPTH = 6

# Pygments tokenises roughly 1.5-2 MB per second, and an upload may be 10 MB. Past this many
# characters only the first part is analysed (functions and depth become lower bounds); the line
# count always covers the whole file. A file this long is "advanced" by its line count anyway.
MAX_ANALYZED_CHARS = 500_000

# Documentation and notes are not code: they count as lines of the upload, not as complexity.
NON_CODE_LANGUAGES = frozenset({"markdown", "text", "unknown"})

_BRACE_LANGUAGES = frozenset({"javascript", "typescript", "java", "c", "cpp", "css"})
_ARROW_FUNCTION_LANGUAGES = frozenset({"javascript", "typescript"})


@dataclass(frozen=True)
class FileMetrics:
    language: str
    lines: int  # non-blank lines
    functions: int
    max_depth: int  # nested blocks; code at the top level of the file is depth 0


@dataclass(frozen=True)
class ComplexityReport:
    level: str
    total_lines: int  # every file, documentation included
    code_lines: int  # what the level was based on
    function_count: int
    max_depth: int


def _python_metrics(text: str) -> tuple[int, int]:
    """Functions and indentation depth. Code that does not tokenize keeps what was read so far."""
    functions = depth = max_depth = 0
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.INDENT:
                depth += 1
                max_depth = max(max_depth, depth)
            elif token.type == tokenize.DEDENT:
                depth -= 1
            elif token.type == tokenize.NAME and token.string == "def":
                functions += 1
    except (tokenize.TokenError, SyntaxError):
        pass
    return functions, max_depth


def _brace_metrics(text: str, language: str) -> tuple[int, int]:
    """Functions and brace depth. Pygments does not tag JavaScript/TypeScript functions or class
    methods, so those are counted by the `function` keyword and `=>` (class methods are missed)."""
    uses_keywords = language in _ARROW_FUNCTION_LANGUAGES
    functions = depth = max_depth = 0
    for token_type, value in get_lexer_by_name(language).get_tokens(text):
        if token_type is Punctuation and value == "{":
            depth += 1
            max_depth = max(max_depth, depth)
        elif token_type is Punctuation and value == "}":
            depth = max(depth - 1, 0)
        elif uses_keywords:
            if (token_type is Keyword.Declaration and value == "function") or (
                token_type is Punctuation and value == "=>"
            ):
                functions += 1
        elif token_type in Name.Function:
            functions += 1
    return functions, max_depth


def measure_source(content: str, language: str) -> FileMetrics:
    """Measure one file. language is a name from language_detector (or normalize_language)."""
    lines = sum(1 for line in content.split("\n") if line.strip())
    text = content[:MAX_ANALYZED_CHARS]
    functions = max_depth = 0
    if language == "python":
        functions, max_depth = _python_metrics(text)
    elif language in _BRACE_LANGUAGES:
        functions, max_depth = _brace_metrics(text, language)
    return FileMetrics(language=language, lines=lines, functions=functions, max_depth=max_depth)


def classify_level(lines: int, functions: int, depth: int) -> str:
    """The most demanding of the three measurements decides."""
    if (
        lines > ADVANCED_ABOVE_LINES
        or functions > ADVANCED_ABOVE_FUNCTIONS
        or depth > ADVANCED_ABOVE_DEPTH
    ):
        return ADVANCED
    if (
        lines <= BEGINNER_MAX_LINES
        and functions <= BEGINNER_MAX_FUNCTIONS
        and depth <= BEGINNER_MAX_DEPTH
    ):
        return BEGINNER
    return INTERMEDIATE


def assess(files: Iterable[FileMetrics]) -> ComplexityReport:
    """Rate a whole upload: code lines and functions add up, the deepest nesting counts.

    An upload without any code (no files, or only documentation) is rated beginner.
    """
    measured = list(files)
    code = [f for f in measured if f.language not in NON_CODE_LANGUAGES]
    code_lines = sum(f.lines for f in code)
    function_count = sum(f.functions for f in code)
    max_depth = max((f.max_depth for f in code), default=0)
    return ComplexityReport(
        level=classify_level(code_lines, function_count, max_depth),
        total_lines=sum(f.lines for f in measured),
        code_lines=code_lines,
        function_count=function_count,
        max_depth=max_depth,
    )
