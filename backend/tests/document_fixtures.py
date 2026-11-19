"""Shared by the document validator and generation service tests."""

from typing import Any

from src.services.ai.prompts import CHAPTER_TITLES, PromptFile

CODE = "".join(f"line{i} = {i}\n" for i in range(1, 14))  # 13 lines
SINGLE = [PromptFile("calc.py", CODE, "python")]
TWO = [PromptFile("a.py", CODE, "python"), PromptFile("b.py", "x = 1\n", "python")]


def concept(n: int) -> dict[str, str]:
    return {
        "name": f"개념{n}",
        "explanation": "쉬운 설명입니다.",
        "analogy": "상자와 같습니다.",
        "example": "x = 1",
        "use_cases": "어디서나 씁니다.",
    }


def valid_doc(path: str = "calc.py") -> dict[str, Any]:
    return {
        "chapter1": {
            "title": CHAPTER_TITLES["chapter1"],
            "summary": "숫자를 더하는 프로그램입니다.",
        },
        "chapter2": {
            "title": CHAPTER_TITLES["chapter2"],
            "concepts": [concept(n) for n in range(1, 6)],
        },
        "chapter3": {
            "title": CHAPTER_TITLES["chapter3"],
            "flowchart": "시작 -> 더하기 -> 끝",
            "file_breakdown": {path: "더하기를 합니다."},
        },
        "chapter4": {
            "title": CHAPTER_TITLES["chapter4"],
            "explanations": [
                {
                    "file": path,
                    "line_start": 1,
                    "line_end": 2,
                    "code": "line1 = 1",
                    "what_it_does": "값을 만듭니다.",
                    "syntax_breakdown": "이름 = 값",
                    "analogy": "라벨 붙은 상자",
                    "alternatives": "x = 5",
                    "notes": "주의할 점",
                }
            ],
        },
        "chapter5": {
            "title": CHAPTER_TITLES["chapter5"],
            "steps": [
                {"step": 1, "description": "첫 단계", "data": "x = 1"},
                {"step": 2, "description": "둘째 단계", "data": "x = 2"},
            ],
        },
        "chapter6": {
            "title": CHAPTER_TITLES["chapter6"],
            "concepts": [
                {
                    "name": "변수",
                    "what_it_is": "상자",
                    "why_its_used": "값을 담으려고",
                    "where_its_applied": "어디서나",
                }
            ],
        },
        "chapter7": {
            "title": CHAPTER_TITLES["chapter7"],
            "mistakes": [
                {"wrong": "x =", "right": "x = 1", "why": "값이 없어서", "fix": "값을 씁니다"}
                for _ in range(3)
            ],
        },
    }
