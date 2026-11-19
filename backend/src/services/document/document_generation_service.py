"""Makes the learning document of a task's code: prompt, AI call, check, and asking again.

Two kinds of trouble are handled, each with its own budget:
  - the AI service is busy or not answering (AIServiceError.retryable): retry up to 3 times with
    exponential backoff, 2 s, 4 s, 8 s plus up to a second of jitter (FR-090, FR-097);
  - the answer is not a valid document: ask again up to 2 times with the problems pointed out
    and a little more freedom in the temperature (FR-096).
Anything else (a rejected request, a blocked prompt, a missing key, a bug) is raised at once.

The service only produces the document. Loading the code, storing the result and tracking the
status are the job of whoever calls it.

Not done, although FR-096 lists them as further fallbacks: accepting a document with some
failed chapters, and building a basic document from the code structure without the AI.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from src.services.ai.errors import AIServiceError
from src.services.ai.gemini_client import GeminiClient, GeminiResponse
from src.services.ai.prompts import PromptFile, build_document_prompt
from src.services.document.document_validator import validate_document
from src.services.document.errors import DocumentGenerationError

logger = logging.getLogger(__name__)

# Temperature of the first request and of each corrected one. The first is 0 so that the same code
# gives the same structure (FR-039); asking again at 0 would only repeat the same mistake.
_TEMPERATURES = (0.0, 0.4, 0.7)
_MAX_PROBLEMS_SHOWN = 10


@dataclass(frozen=True)
class RetryEvent:
    """About to wait and ask again. Lets the caller show "retrying..." (FR-093)."""

    kind: str  # "service": the AI was unavailable; "quality": the answer was not usable
    attempt: int  # which retry of its kind this is, from 1
    max_attempts: int  # how many retries of this kind are allowed
    delay_seconds: float | None  # how long it waits first (service only)
    reason: str  # an error code, or the first problems


@dataclass(frozen=True)
class GeneratedDocument:
    content: dict[str, Any]  # cleaned: the shape of learning_documents.content
    truncated: bool  # the code was too long to send whole
    model: str
    model_calls: int  # every call to the AI, failed ones included
    prompt_tokens: int  # the totals of all answers received
    completion_tokens: int
    thinking_tokens: int


def _correction(prompt: str, problems: list[str]) -> str:
    """The original request plus what was wrong. Built only from the validator's own words."""
    shown = problems[:_MAX_PROBLEMS_SHOWN]
    lines = [f"- {problem}" for problem in shown]
    if len(problems) > len(shown):
        lines.append(f"- 그 밖에 {len(problems) - len(shown)}개의 문제가 더 있습니다.")
    return (
        f"{prompt}\n\n# 수정 요청\n"
        "이전 답변은 아래 문제 때문에 사용할 수 없었습니다. "
        "같은 구조로 JSON 하나만 다시 출력하세요.\n" + "\n".join(lines)
    )


class DocumentGenerationService:
    def __init__(
        self,
        client: GeminiClient,
        *,
        max_retries: int = 3,
        max_quality_retries: int = 2,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        request_timeout: float = 150.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
        on_retry: Callable[[RetryEvent], Awaitable[None]] | None = None,
    ) -> None:
        self.client = client
        self.max_retries = max_retries
        self.max_quality_retries = max_quality_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.request_timeout = request_timeout
        self._sleep = sleep
        self._jitter = jitter  # seconds below 1
        self._on_retry = on_retry
        self._calls = 0

    async def generate(
        self, files: Sequence[PromptFile], *, language: str, complexity_level: str
    ) -> GeneratedDocument:
        """The validated document for `files`, or an AIServiceError saying why there is none."""
        built = build_document_prompt(files, language=language, complexity_level=complexity_level)
        self._calls = 0
        prompt = built.prompt
        usage = [0, 0, 0]
        quality_retry = 0
        while True:
            temperature = _TEMPERATURES[min(quality_retry, len(_TEMPERATURES) - 1)]
            response = await self._ask(prompt, built.system_instruction, temperature)
            for index, tokens in enumerate(
                (response.prompt_tokens, response.completion_tokens, response.thinking_tokens)
            ):
                usage[index] += tokens or 0
            result = validate_document(response.text, files)
            if result.content is not None:
                return GeneratedDocument(
                    content=result.content,
                    truncated=built.truncated,
                    model=response.model,
                    model_calls=self._calls,
                    prompt_tokens=usage[0],
                    completion_tokens=usage[1],
                    thinking_tokens=usage[2],
                )
            if quality_retry >= self.max_quality_retries:
                raise DocumentGenerationError(result.problems, model_calls=self._calls)
            quality_retry += 1
            await self._announce(
                RetryEvent(
                    "quality",
                    quality_retry,
                    self.max_quality_retries,
                    None,
                    "; ".join(result.problems[:3]),
                )
            )
            prompt = _correction(built.prompt, result.problems)

    async def _ask(
        self, prompt: str, system_instruction: str, temperature: float
    ) -> GeminiResponse:
        """One answer from the AI, waiting and trying again while the service is unavailable."""
        for retry in range(self.max_retries + 1):
            self._calls += 1
            try:
                return await self.client.generate(
                    prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    json_output=True,
                    timeout=self.request_timeout,
                )
            except AIServiceError as exc:
                if not exc.retryable or retry == self.max_retries:
                    raise
                delay = min(self.max_delay, self.base_delay * 2**retry + self._jitter())
                await self._announce(
                    RetryEvent("service", retry + 1, self.max_retries, delay, exc.code)
                )
                await self._sleep(delay)
        raise AssertionError(
            "unreachable: the last retry either returns or raises"
        )  # pragma: no cover

    async def _announce(self, event: RetryEvent) -> None:
        logger.warning(
            "Document generation retry: kind=%s attempt=%s/%s reason=%s",
            event.kind,
            event.attempt,
            event.max_attempts,
            event.reason,
        )
        if self._on_retry is not None:
            await self._on_retry(event)
