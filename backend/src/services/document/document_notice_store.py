"""The "retrying..." note of a document being generated, kept in Redis for a few minutes.

The worker writes it between retries and the status endpoint reads it. It is only a courtesy:
every failure of Redis (not running, slow, refused) is swallowed, so a missing note never breaks
the generation or the status call. Only the kind of error is logged, never its text, which may
carry the connection URL with its password.
"""

import logging
import uuid
from typing import Any

import redis.asyncio

from src.services.document.document_generation_service import RetryEvent

logger = logging.getLogger(__name__)

NOTICE_TTL_SECONDS = 300
# A status call must not wait long for a Redis that is down.
_SOCKET_TIMEOUT_SECONDS = 1


def notice_text(event: RetryEvent) -> str:
    if event.kind == "service":
        return f"AI 서비스가 바빠 다시 시도하는 중입니다 ({event.attempt}/{event.max_attempts})."
    return f"AI 응답을 다듬어 다시 요청하는 중입니다 ({event.attempt}/{event.max_attempts})."


def _key(task_id: uuid.UUID) -> str:
    return f"document:notice:{task_id}"


class NoticeStore:
    def __init__(self, client: Any | None) -> None:
        self.client = client  # a redis.asyncio client (decode_responses=True), or None for none

    @classmethod
    def from_url(cls, url: str) -> "NoticeStore":
        """A client that connects on first use, so building one never needs Redis."""
        return cls(
            redis.asyncio.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=_SOCKET_TIMEOUT_SECONDS,
                socket_timeout=_SOCKET_TIMEOUT_SECONDS,
            )
        )

    async def set(self, task_id: uuid.UUID, text: str) -> None:
        if self.client is None:
            return
        try:
            await self.client.set(_key(task_id), text, ex=NOTICE_TTL_SECONDS)
        except Exception as exc:
            self._unavailable(exc)

    async def get(self, task_id: uuid.UUID) -> str | None:
        if self.client is None:
            return None
        try:
            value: str | None = await self.client.get(_key(task_id))
        except Exception as exc:
            self._unavailable(exc)
            return None
        return value

    async def clear(self, task_id: uuid.UUID) -> None:
        if self.client is None:
            return
        try:
            await self.client.delete(_key(task_id))
        except Exception as exc:
            self._unavailable(exc)

    async def aclose(self) -> None:
        if self.client is None:
            return
        try:
            await self.client.aclose()
        except Exception as exc:
            self._unavailable(exc)

    @staticmethod
    def _unavailable(exc: Exception) -> None:
        logger.warning("Document notice store unavailable: %s", type(exc).__name__)
