import uuid

import pytest
import redis.asyncio
from src.services.document.document_generation_service import RetryEvent
from src.services.document.document_notice_store import (
    NOTICE_TTL_SECONDS,
    NoticeStore,
    notice_text,
)
from tests.queue_helpers import DownRedis, MemoryRedis

TASK = uuid.UUID("11111111-1111-1111-1111-111111111111")


def event(kind: str, attempt: int = 1, maximum: int = 3) -> RetryEvent:
    return RetryEvent(kind, attempt, maximum, None, "reason")


def test_service_retry_text() -> None:
    assert notice_text(event("service", 1, 3)) == "AI 서비스가 바빠 다시 시도하는 중입니다 (1/3)."


def test_quality_retry_text() -> None:
    assert notice_text(event("quality", 2, 2)) == "AI 응답을 다듬어 다시 요청하는 중입니다 (2/2)."


async def test_set_get_clear_with_ttl_and_per_task_key() -> None:
    fake = MemoryRedis()
    store = NoticeStore(fake)
    await store.set(TASK, "안내")
    assert await store.get(TASK) == "안내"
    assert await store.get(uuid.uuid4()) is None
    assert fake.ttls[f"document:notice:{TASK}"] == NOTICE_TTL_SECONDS == 300
    await store.set(TASK, "다음 안내")
    assert await store.get(TASK) == "다음 안내"
    await store.clear(TASK)
    assert await store.get(TASK) is None


async def test_without_a_client_everything_is_quiet() -> None:
    store = NoticeStore(None)
    await store.set(TASK, "안내")
    assert await store.get(TASK) is None
    await store.clear(TASK)
    await store.aclose()


async def test_redis_failures_are_silent_and_not_logged_with_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = NoticeStore(DownRedis())
    await store.set(TASK, "안내")
    assert await store.get(TASK) is None
    await store.clear(TASK)
    await store.aclose()
    assert "topsecret" not in caplog.text


async def test_aclose_closes_the_client() -> None:
    fake = MemoryRedis()
    await NoticeStore(fake).aclose()
    assert fake.closed is True


async def test_from_url_builds_a_lazy_client_without_connecting() -> None:
    store = NoticeStore.from_url("redis://127.0.0.1:1/0")  # nothing listens there
    assert isinstance(store.client, redis.asyncio.Redis)
    assert await store.get(TASK) is None  # connection refused: quiet
    await store.aclose()
