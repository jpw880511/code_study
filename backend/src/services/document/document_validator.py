"""Checks the AI's answer for a learning document and cleans it for storage.

The answer must be a JSON object that follows OUTPUT_SKELETON: every chapter, every field, the
right types, real text instead of the skeleton's placeholders (FR-095 as far as it applies to the
stored structure). Nothing is repaired except what cannot hurt:
  - fields the structure does not know are dropped, so only the known shape is ever stored;
  - the chapter titles are the fixed ones, whatever the AI wrote (FR-039);
  - more than 5 concepts or 5 mistakes are cut to 5 (FR-029, FR-034);
  - step numbers are made sequential, and with a single uploaded file the file name is set.
Everything else that is wrong is a problem. All problems are collected, in words made from field
paths only: they are fed back to the AI to ask for a better answer and must never repeat what
the AI wrote.

Not checked: HTML in the text. A learner may upload HTML, whose explanation legitimately shows
tags; the document must be shown as plain text (never as HTML) wherever it is displayed.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from src.models.learning_document import CHAPTER_KEYS
from src.services.ai.prompts import CHAPTER_TITLES, OUTPUT_SKELETON, PromptFile, split_lines

# (minimum, maximum) number of items of a list; maximum None = no limit. Others: at least one.
_LIMITS: dict[str, tuple[int, int | None]] = {
    "chapter2.concepts": (1, 5),
    "chapter7.mistakes": (3, 5),
}
# Details of the line by line chapter that the AI may fairly leave empty for a trivial line.
_MAY_BE_EMPTY = frozenset(
    {
        "chapter4.explanations.syntax_breakdown",
        "chapter4.explanations.analogy",
        "chapter4.explanations.alternatives",
        "chapter4.explanations.notes",
        "chapter5.steps.data",
    }
)
_FENCED = re.compile(r"`{3,}[A-Za-z]*[ \t]*\n(.*?)\n?`{3,}", re.DOTALL)
_INDEX = re.compile(r"\[\d+\]")
_TODO_MARKERS = ("[todo]", "[generate]")
_FILE_BREAKDOWN = "chapter3.file_breakdown"


def _placeholders() -> frozenset[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.startswith("<"):
                    found.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str) and node.startswith("<"):
            found.add(node)

    walk(OUTPUT_SKELETON)
    return frozenset(found)


PLACEHOLDERS = _placeholders()


@dataclass(frozen=True)
class ValidationResult:
    content: dict[str, Any] | None  # the cleaned document, only when there are no problems
    problems: list[str]


def parse_json_answer(text: str) -> Any:
    """The JSON in the answer, also when the AI wrapped it in a markdown code fence."""
    stripped = text.strip()
    fenced = _FENCED.fullmatch(stripped)
    if fenced:
        stripped = fenced.group(1)
    try:
        return json.loads(stripped)
    except RecursionError as exc:  # a pathologically nested answer
        raise ValueError("JSON is nested too deeply") from exc


def _is_placeholder(text: str) -> bool:
    lowered = text.strip().lower()
    return text.strip() in PLACEHOLDERS or any(marker in lowered for marker in _TODO_MARKERS)


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _clean_text(value: Any, path: str, problems: list[str]) -> str | None:
    if not isinstance(value, str):
        problems.append(f"{path}: 문자열이어야 합니다.")
        return None
    if _is_placeholder(value):
        problems.append(f"{path}: 예시 문구나 TODO가 그대로 남아 있습니다.")
        return None
    if not value.strip() and _INDEX.sub("", path) not in _MAY_BE_EMPTY:
        problems.append(f"{path}: 비어 있습니다.")
        return None
    return value


def _clean_breakdown(value: Any, path: str, problems: list[str]) -> dict[str, str] | None:
    """file path -> what the file does: free keys, so it is not checked against the skeleton."""
    if not isinstance(value, dict):
        problems.append(f"{path}: 객체여야 합니다.")
        return None
    if not value:
        problems.append(f"{path}: 비어 있습니다.")
        return None
    if any(_is_placeholder(str(key)) for key in value):
        problems.append(f"{path}: 예시 문구나 TODO가 그대로 남아 있습니다.")
        return None
    if not all(isinstance(text, str) for text in value.values()):
        problems.append(f"{path}: 값이 문자열이어야 합니다.")
        return None
    return {str(key): text for key, text in value.items()}


def _clean(value: Any, template: Any, path: str, problems: list[str]) -> Any:
    """`value` cut to the shape of `template`; problems are appended, None stands for a miss."""
    if isinstance(template, dict):
        if _INDEX.sub("", path) == _FILE_BREAKDOWN:
            return _clean_breakdown(value, path, problems)
        if not isinstance(value, dict):
            problems.append(f"{path}: 객체여야 합니다.")
            return None
        cleaned: dict[str, Any] = {}
        for key, sub in template.items():
            if key not in value:
                problems.append(f"{_join(path, key)}: 빠졌습니다.")
                continue
            cleaned[key] = _clean(value[key], sub, _join(path, key), problems)
        return cleaned
    if isinstance(template, list):
        if not isinstance(value, list):
            problems.append(f"{path}: 목록이어야 합니다.")
            return None
        low, high = _LIMITS.get(_INDEX.sub("", path), (1, None))
        if len(value) < low:
            problems.append(f"{path}: 항목이 {low}개 이상이어야 합니다 (지금 {len(value)}개).")
            return None
        items = value if high is None else value[:high]  # the cut-off items are not looked at
        return [_clean(item, template[0], f"{path}[{n}]", problems) for n, item in enumerate(items)]
    if isinstance(template, int):
        if isinstance(value, bool) or not isinstance(value, int):
            problems.append(f"{path}: 정수여야 합니다.")
            return None
        return value
    return _clean_text(value, path, problems)


def _check_line_by_line(
    chapter: dict[str, Any], files: Sequence[PromptFile], problems: list[str]
) -> None:
    line_counts = {file.path: len(split_lines(file.content)) for file in files}
    for number, item in enumerate(chapter["explanations"]):
        where = f"chapter4.explanations[{number}]"
        if item["file"] not in line_counts:
            if len(files) == 1:
                item["file"] = files[0].path  # nothing else it can mean
            else:
                problems.append(f"{where}.file: 업로드한 파일 경로가 아닙니다.")
                continue
        total = line_counts[item["file"]]
        if not 1 <= item["line_start"] <= item["line_end"] <= total:
            problems.append(
                f"{where}: 줄 번호는 1 이상이고 시작 ≤ 끝 ≤ 파일 줄 수({total})여야 합니다."
            )


def validate_document(text: str, files: Sequence[PromptFile]) -> ValidationResult:
    """The cleaned document for `text` (the AI's answer about `files`), or the problems."""
    try:
        answer = parse_json_answer(text)
    except ValueError:
        return ValidationResult(None, ["응답이 올바른 JSON이 아닙니다."])
    if not isinstance(answer, dict):
        return ValidationResult(None, ["최상위가 객체여야 합니다."])

    problems: list[str] = []
    content: dict[str, Any] = {}
    for key in CHAPTER_KEYS:
        if key not in answer:
            problems.append(f"{key}: 빠졌습니다.")
            continue
        template = {name: sub for name, sub in OUTPUT_SKELETON[key].items() if name != "title"}
        before = len(problems)
        chapter = _clean(answer[key], template, key, problems)
        if len(problems) == before and isinstance(chapter, dict):
            if key == "chapter4":
                _check_line_by_line(chapter, files, problems)
            elif key == "chapter5":
                for number, step in enumerate(chapter["steps"], start=1):
                    step["step"] = number
            content[key] = {"title": CHAPTER_TITLES[key], **chapter}
    if problems:
        return ValidationResult(None, problems)
    return ValidationResult(content, [])
