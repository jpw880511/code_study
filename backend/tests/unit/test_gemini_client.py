import asyncio
import logging
import os
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from google.genai import errors, types
from pydantic import SecretStr
from src.services.ai import gemini_client
from src.services.ai.config import GeminiSettings
from src.services.ai.errors import (
    AINotConfiguredError,
    AIRequestRejectedError,
    AIResponseError,
    AIServiceError,
    AIServiceUnavailableError,
)
from src.services.ai.gemini_client import GeminiClient, GeminiResponse
from src.services.errors import DomainError

PROMPT = "def add(a, b): return a + b  # 비밀 학습자 코드"


def reply(
    text: str | None = "안녕하세요",
    *,
    finish: str = "STOP",
    prompt_tokens: int | None = 12,
    output_tokens: int | None = 34,
    thinking_tokens: int | None = None,
    block_reason: str | None = None,
) -> types.GenerateContentResponse:
    candidates = []
    if text is not None:
        candidates.append(
            types.Candidate(
                content=types.Content(parts=[types.Part(text=text)]),
                finish_reason=types.FinishReason(finish),
            )
        )
    elif not block_reason:
        candidates.append(types.Candidate(finish_reason=types.FinishReason(finish)))
    return types.GenerateContentResponse(
        candidates=candidates,
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt_tokens,
            candidates_token_count=output_tokens,
            thoughts_token_count=thinking_tokens,
        )
        if prompt_tokens is not None
        else None,
        prompt_feedback=types.GenerateContentResponsePromptFeedback(
            block_reason=types.BlockedReason(block_reason)
        )
        if block_reason
        else None,
    )


class FakeSdk:
    """Just enough of google.genai.Client: client.aio.models.generate_content."""

    def __init__(self, outcome: Any = None) -> None:
        if isinstance(outcome, BaseException):
            self.generate_content = AsyncMock(side_effect=outcome)  # raised, not returned
        else:
            self.generate_content = AsyncMock(return_value=reply() if outcome is None else outcome)
        self.close_async = AsyncMock()
        self.aio = type("Aio", (), {"models": self, "aclose": self.close_async})()


def make_client(outcome: Any = None, **settings: Any) -> tuple[GeminiClient, FakeSdk]:
    sdk = FakeSdk(outcome)
    client = GeminiClient(GeminiSettings(**settings), sdk_client=sdk)  # type: ignore[arg-type]
    return client, sdk


def config_of(sdk: FakeSdk) -> types.GenerateContentConfig:
    config = sdk.generate_content.call_args.kwargs["config"]
    assert isinstance(config, types.GenerateContentConfig)
    return config


# ------------------------------------------------------------- the happy path


async def test_generate_returns_the_text_the_model_and_the_usage() -> None:
    client, _ = make_client(
        reply("설명입니다", prompt_tokens=7, output_tokens=9, thinking_tokens=41)
    )
    response = await client.generate(PROMPT)
    assert response == GeminiResponse(
        text="설명입니다",
        model="gemini-3-flash-preview",
        prompt_tokens=7,
        completion_tokens=9,
        thinking_tokens=41,
        finish_reason="STOP",
    )


async def test_the_prompt_and_the_configured_model_reach_the_sdk() -> None:
    client, sdk = make_client(gemini_model="gemini-other")
    await client.generate(PROMPT)
    kwargs = sdk.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-other"
    assert kwargs["contents"] == PROMPT


async def test_options_that_were_not_given_are_left_out_of_the_request() -> None:
    client, sdk = make_client()
    await client.generate(PROMPT)
    config = config_of(sdk)
    assert config.system_instruction is None
    assert config.temperature is None
    assert config.max_output_tokens is None
    assert config.response_mime_type is None


async def test_the_options_are_passed_on() -> None:
    client, sdk = make_client()
    await client.generate(
        PROMPT,
        system_instruction="초보자에게 설명하세요",
        temperature=0.3,
        max_output_tokens=2048,
        json_output=True,
    )
    config = config_of(sdk)
    assert config.system_instruction == "초보자에게 설명하세요"
    assert config.temperature == 0.3
    assert config.max_output_tokens == 2048
    assert config.response_mime_type == "application/json"


async def test_the_timeout_comes_from_the_settings_and_can_be_set_per_call() -> None:
    client, sdk = make_client(timeout_seconds=90)
    await client.generate(PROMPT)
    assert config_of(sdk).http_options is not None
    assert config_of(sdk).http_options.timeout == 90_000  # milliseconds
    await client.generate(PROMPT, timeout=10)
    assert config_of(sdk).http_options.timeout == 10_000


async def test_truncated_output_is_returned_and_flagged_for_the_caller() -> None:
    client, _ = make_client(reply('{"chapter1": {', finish="MAX_TOKENS"))
    response = await client.generate(PROMPT)
    assert response.text == '{"chapter1": {'
    assert response.finish_reason == "MAX_TOKENS"


async def test_missing_usage_information_is_none() -> None:
    client, _ = make_client(reply("ok", prompt_tokens=None))
    response = await client.generate(PROMPT)
    assert (response.prompt_tokens, response.completion_tokens, response.thinking_tokens) == (
        None,
        None,
        None,
    )


# -------------------------------------------------------------- closing the client


async def test_closing_closes_the_async_side_of_the_sdk_once() -> None:
    client, sdk = make_client()
    await client.generate(PROMPT)
    await client.aclose()
    await client.aclose()  # closing twice is harmless
    sdk.close_async.assert_awaited_once()


async def test_closing_a_client_that_never_made_a_call_creates_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def must_not_be_called(**_: Any) -> FakeSdk:
        raise AssertionError("closing must not create an SDK client")

    monkeypatch.setattr(gemini_client.genai, "Client", must_not_be_called)
    await GeminiClient(GeminiSettings(google_api_key=SecretStr("k"))).aclose()


async def test_a_closed_client_can_be_used_again(monkeypatch: pytest.MonkeyPatch) -> None:
    made: list[FakeSdk] = []

    def fake_client(*, api_key: str) -> FakeSdk:
        made.append(FakeSdk())
        return made[-1]

    monkeypatch.setattr(gemini_client.genai, "Client", fake_client)
    client = GeminiClient(GeminiSettings(google_api_key=SecretStr("k")))
    await client.generate(PROMPT)
    await client.aclose()
    await client.generate(PROMPT)  # a fresh SDK client, not the closed one
    assert len(made) == 2
    made[0].close_async.assert_awaited_once()
    made[1].close_async.assert_not_awaited()


# ------------------------------------------------------- creating the real SDK


def test_a_real_key_from_the_developers_env_never_reaches_a_test() -> None:
    # alembic/env.py loads the repo's .env into os.environ when a DB test migrates. The shared
    # guard in conftest removes the AI settings again before every test; this file has no
    # cleaning of its own, so it fails if that guard goes away.
    assert "GOOGLE_API_KEY" not in os.environ
    assert GeminiSettings().google_api_key is None


async def test_without_a_key_it_refuses_at_call_time_not_at_start_up() -> None:
    client = GeminiClient(GeminiSettings())  # building the client must not need a key
    with pytest.raises(AINotConfiguredError) as raised:
        await client.generate(PROMPT)
    assert raised.value.retryable is False


async def test_the_sdk_is_created_once_with_the_unwrapped_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[str] = []

    def fake_client(*, api_key: str) -> FakeSdk:
        created.append(api_key)
        return FakeSdk()

    monkeypatch.setattr(gemini_client.genai, "Client", fake_client)
    client = GeminiClient(GeminiSettings(google_api_key=SecretStr("the-real-key")))
    await client.generate(PROMPT)
    await client.generate(PROMPT)
    assert created == ["the-real-key"]


async def test_default_settings_are_read_when_none_are_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "key-from-environment")
    monkeypatch.setenv("GEMINI_MODEL", "model-from-environment")
    seen: list[str] = []

    def fake_client(*, api_key: str) -> FakeSdk:
        seen.append(api_key)
        return FakeSdk()

    monkeypatch.setattr(gemini_client.genai, "Client", fake_client)
    response = await GeminiClient().generate(PROMPT)
    assert seen == ["key-from-environment"]
    assert response.model == "model-from-environment"


# ----------------------------------------------------------------- failures


def api_error(status: int, message: str = "upstream says no") -> errors.APIError:
    body = {"error": {"message": message, "status": "SOME_STATUS"}}
    return (errors.ServerError if status >= 500 else errors.ClientError)(status, body)


@pytest.mark.parametrize("status", [500, 502, 503, 504, 429, 408])
async def test_a_busy_or_broken_service_is_worth_retrying(status: int) -> None:
    client, _ = make_client(api_error(status))
    with pytest.raises(AIServiceUnavailableError) as raised:
        await client.generate(PROMPT)
    assert raised.value.retryable is True
    assert raised.value.status_code == status
    assert raised.value.code == "ai_unavailable"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
async def test_a_rejected_request_is_not_worth_retrying(status: int) -> None:
    client, _ = make_client(api_error(status))
    with pytest.raises(AIRequestRejectedError) as raised:
        await client.generate(PROMPT)
    assert raised.value.retryable is False
    assert raised.value.status_code == status
    assert raised.value.code == "ai_request_rejected"


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ReadTimeout("slow"),
        httpx.ConnectTimeout("slow"),
        httpx.ConnectError("no route"),
        httpx.RemoteProtocolError("dropped"),
        TimeoutError(),
        ConnectionResetError(),
    ],
    ids=lambda f: type(f).__name__,
)
async def test_a_timeout_or_a_network_failure_is_worth_retrying(failure: Exception) -> None:
    client, _ = make_client(failure)
    with pytest.raises(AIServiceUnavailableError) as raised:
        await client.generate(PROMPT)
    assert raised.value.retryable is True
    assert raised.value.status_code is None


async def test_the_original_error_is_kept_as_the_cause() -> None:
    original = api_error(503)
    client, _ = make_client(original)
    with pytest.raises(AIServiceUnavailableError) as raised:
        await client.generate(PROMPT)
    assert raised.value.__cause__ is original


async def test_a_bug_is_not_disguised_as_an_ai_problem() -> None:
    client, _ = make_client(ValueError("a programming mistake"))
    with pytest.raises(ValueError, match="a programming mistake"):
        await client.generate(PROMPT)


async def test_cancelling_the_call_is_never_swallowed() -> None:
    client, _ = make_client(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await client.generate(PROMPT)


@pytest.mark.parametrize("block_reason", ["SAFETY", "OTHER", "PROHIBITED_CONTENT"])
async def test_a_blocked_prompt_is_reported_with_the_reason(block_reason: str) -> None:
    client, _ = make_client(reply(None, block_reason=block_reason))
    with pytest.raises(AIResponseError) as raised:
        await client.generate(PROMPT)
    assert raised.value.retryable is False
    assert raised.value.reason == block_reason
    assert raised.value.code == "ai_response_invalid"


async def test_an_answer_that_was_cut_off_by_the_safety_filter_is_an_error() -> None:
    client, _ = make_client(reply(None, finish="SAFETY"))
    with pytest.raises(AIResponseError) as raised:
        await client.generate(PROMPT)
    assert raised.value.reason == "SAFETY"


async def test_an_answer_without_any_candidate_is_an_error() -> None:
    client, _ = make_client(types.GenerateContentResponse(candidates=[]))
    with pytest.raises(AIResponseError) as raised:
        await client.generate(PROMPT)
    assert raised.value.reason == "empty_response"


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
async def test_an_answer_with_only_blank_text_is_an_error(text: str) -> None:
    client, _ = make_client(reply(text))
    with pytest.raises(AIResponseError) as raised:
        await client.generate(PROMPT)
    assert raised.value.reason == "STOP"


# --------------------------------------------------------- what must not leak


async def test_messages_are_korean_and_say_nothing_about_the_upstream_error() -> None:
    client, _ = make_client(api_error(503, "SECRET-KEY-123 and details nobody should see"))
    with pytest.raises(AIServiceUnavailableError) as raised:
        await client.generate(PROMPT)
    message = raised.value.message
    assert "AI 서비스" in message
    assert "SECRET-KEY-123" not in message
    assert "SECRET-KEY-123" not in str(raised.value)


async def test_failures_are_logged_without_the_prompt_or_the_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = make_client(api_error(503, "SECRET-KEY-123"), google_api_key=SecretStr("my-key"))
    with caplog.at_level(logging.WARNING, logger=gemini_client.logger.name):
        with pytest.raises(AIServiceUnavailableError):
            await client.generate(PROMPT)
    logged = caplog.text
    assert "gemini-3-flash-preview" in logged
    assert "503" in logged
    assert "비밀 학습자 코드" not in logged
    assert "my-key" not in logged
    assert "SECRET-KEY-123" not in logged


def test_the_errors_are_domain_errors_with_their_own_codes() -> None:
    classes = [
        AINotConfiguredError,
        AIServiceUnavailableError,
        AIRequestRejectedError,
        AIResponseError,
    ]
    assert all(issubclass(c, AIServiceError) and issubclass(c, DomainError) for c in classes)
    codes = [c.code for c in classes]
    assert len(set(codes)) == len(codes)
    assert [c.retryable for c in classes] == [False, True, False, False]
