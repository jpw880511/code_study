"""A thin client for Google Gemini: one call in, one text out, and failures sorted by whether
asking again may help.

It does not retry. Retrying (3 times with exponential backoff, FR-090) belongs to the callers,
document generation and Q&A, which differ in how long they may wait; this client gives them
`AIServiceError.retryable` to decide with. It also never logs or puts into an error message the
prompt (the learner's code), the answer or the key.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from src.services.ai.config import GeminiSettings
from src.services.ai.errors import (
    AINotConfiguredError,
    AIRequestRejectedError,
    AIResponseError,
    AIServiceUnavailableError,
)

logger = logging.getLogger(__name__)

# 408 and 429 are the client-side statuses that mean "try again later".
_RETRYABLE_STATUSES = frozenset({408, 429})
# Timeouts, refused or dropped connections: the service may be fine a moment later.
_NETWORK_ERRORS = (httpx.TransportError, TimeoutError, ConnectionError)


@dataclass(frozen=True)
class GeminiResponse:
    text: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None  # the visible answer only
    # What the model spent thinking before it answered. It counts against max_output_tokens
    # but not against completion_tokens, so it is what explains "the cap was reached and there
    # is no text" (see generate()) and it is billed.
    thinking_tokens: int | None
    # "STOP" is a normal end; "MAX_TOKENS" means the text was cut off (a JSON answer would be
    # incomplete), which only the caller can judge.
    finish_reason: str | None


def _name(value: Any) -> str:
    """Enum name of a finish or block reason ("SAFETY"), or its text."""
    return str(getattr(value, "name", value))


class GeminiClient:
    def __init__(
        self, settings: GeminiSettings | None = None, *, sdk_client: genai.Client | None = None
    ) -> None:
        self.settings = settings or GeminiSettings()
        self._sdk_client = sdk_client  # tests hand in a fake; otherwise built on first use

    @property
    def model(self) -> str:
        return self.settings.gemini_model

    def _sdk(self) -> genai.Client:
        if self._sdk_client is None:
            key = self.settings.google_api_key
            if key is None:
                raise AINotConfiguredError()
            self._sdk_client = genai.Client(api_key=key.get_secret_value())
        return self._sdk_client

    async def aclose(self) -> None:
        """Close the SDK's HTTP connections; call it before the event loop that used them ends.

        Connections left open are closed by a finalizer after the loop is gone, which fails with
        "Event loop is closed" and leaves a traceback in the log (seen in a Celery worker, where
        every job runs in its own asyncio.run). Safe to call twice or without any call made; a
        later call to generate() builds a fresh SDK client.
        """
        sdk, self._sdk_client = self._sdk_client, None
        if sdk is not None:
            await sdk.aio.aclose()

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        json_output: bool = False,
        timeout: float | None = None,
    ) -> GeminiResponse:
        """Ask the model once. Raises an AIServiceError subclass if that gives no usable text.

        max_output_tokens includes the model's thinking tokens on Gemini 3 (measured with
        gemini-3-flash-preview: even "1+1?" needs about 70 of them). A small cap such as 50 is
        used up by thinking and the answer comes back empty (AIResponseError, reason MAX_TOKENS).
        Leave it unset, or keep it generous, for anything longer than a one-word answer.
        """
        sdk = self._sdk()
        seconds = timeout if timeout is not None else self.settings.timeout_seconds
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json" if json_output else None,
            http_options=types.HttpOptions(timeout=int(seconds * 1000)),  # milliseconds
        )
        try:
            result = await sdk.aio.models.generate_content(
                model=self.model, contents=prompt, config=config
            )
        except errors.APIError as exc:
            status = exc.code
            self._log_failure(status, exc)
            if status >= 500 or status in _RETRYABLE_STATUSES:
                raise AIServiceUnavailableError(status_code=status) from exc
            raise AIRequestRejectedError(status_code=status) from exc
        except _NETWORK_ERRORS as exc:
            self._log_failure(None, exc)
            raise AIServiceUnavailableError() from exc
        return self._read(result)

    def _read(self, result: types.GenerateContentResponse) -> GeminiResponse:
        feedback = result.prompt_feedback
        if feedback is not None and feedback.block_reason is not None:
            raise AIResponseError(reason=_name(feedback.block_reason))
        candidate = result.candidates[0] if result.candidates else None
        finish = _name(candidate.finish_reason) if candidate and candidate.finish_reason else None
        text = result.text  # None when there is no candidate or it has no text
        if text is None or not text.strip():
            raise AIResponseError(reason=finish or "empty_response")
        usage = result.usage_metadata
        return GeminiResponse(
            text=text,
            model=self.model,
            prompt_tokens=usage.prompt_token_count if usage else None,
            completion_tokens=usage.candidates_token_count if usage else None,
            thinking_tokens=usage.thoughts_token_count if usage else None,
            finish_reason=finish,
        )

    def _log_failure(self, status: int | None, exc: Exception) -> None:
        logger.warning(
            "Gemini request failed: model=%s status=%s error=%s",
            self.model,
            status,
            type(exc).__name__,
        )
