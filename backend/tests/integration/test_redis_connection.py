import os
from collections.abc import Iterator

import pytest
import redis
from celery.contrib.testing.worker import start_worker
from src.tasks.celery_app import QUEUE_NAMES, create_celery_app

BASE_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture(scope="module")
def redis_client() -> Iterator[redis.Redis]:
    client = redis.Redis.from_url(BASE_URL)
    try:
        client.ping()
    except redis.exceptions.ConnectionError as exc:
        pytest.skip(f"Redis is not reachable: {exc}")
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


def test_celery_connects_to_redis_broker(redis_client: redis.Redis) -> None:
    app = create_celery_app(BASE_URL)
    with app.connection_for_write() as connection:
        connection.ensure_connection(max_retries=1)
        assert connection.connected


def test_result_backend_is_reachable(redis_client: redis.Redis) -> None:
    app = create_celery_app(BASE_URL)
    assert app.backend.client.ping() is True


def test_task_round_trip_through_real_worker(redis_client: redis.Redis) -> None:
    app = create_celery_app(BASE_URL)

    @app.task(name="tests.add")
    def add(x: int, y: int) -> int:
        return x + y

    with start_worker(app, pool="solo", perform_ping_check=False, queues=["default"]):
        result = add.apply_async((4, 5), queue="default")
        assert result.get(timeout=30) == 9


@pytest.mark.parametrize("queue", ["document_generation", "practice_generation", "cleanup"])
def test_task_is_delivered_only_to_the_requested_queue(
    redis_client: redis.Redis, queue: str
) -> None:
    app = create_celery_app(BASE_URL)

    @app.task(name="tests.noop")
    def noop() -> None:
        return None

    redis_client.flushdb()
    # A running worker declares (binds) every queue; do the same before publishing.
    with app.connection_for_write() as connection:
        for declared in app.amqp.queues.values():
            declared(connection.default_channel).declare()
    noop.apply_async(queue=queue)
    lengths = {name: redis_client.llen(name) for name in QUEUE_NAMES}
    assert lengths == {name: int(name == queue) for name in QUEUE_NAMES}
