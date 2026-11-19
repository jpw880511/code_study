import pytest
from celery import Celery
from pydantic import ValidationError
from src.tasks.celery_app import (
    QUEUE_NAMES,
    TASK_TIME_LIMIT_SECONDS,
    RedisSettings,
    celery_app,
    create_celery_app,
)

URL = "redis://example-host:6380/3"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)


def test_module_level_app_is_celery() -> None:
    assert isinstance(celery_app, Celery)
    assert celery_app.main == "code_study"


def test_queues_follow_the_constitution() -> None:
    assert QUEUE_NAMES == ("default", "document_generation", "practice_generation", "cleanup")
    app = create_celery_app(URL)
    declared = {queue.name for queue in app.conf.task_queues}
    assert declared == set(QUEUE_NAMES)
    assert app.conf.task_default_queue == "default"


def test_each_queue_has_its_own_exchange_and_routing_key() -> None:
    queues = dict(create_celery_app(URL).amqp.queues)
    for name in QUEUE_NAMES:
        assert queues[name].routing_key == name
        assert queues[name].exchange.name == name
    assert len({queue.exchange.name for queue in queues.values()}) == len(QUEUE_NAMES)


def test_task_timeout_is_300_seconds() -> None:
    assert TASK_TIME_LIMIT_SECONDS == 300
    assert create_celery_app(URL).conf.task_time_limit == 300


def test_json_only_serialization_and_utc() -> None:
    conf = create_celery_app(URL).conf
    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert list(conf.accept_content) == ["json"]
    assert conf.timezone == "UTC"
    assert conf.enable_utc is True


def test_workers_reconnect_to_the_broker_on_startup() -> None:
    assert create_celery_app(URL).conf.broker_connection_retry_on_startup is True


def test_started_state_is_tracked() -> None:
    assert create_celery_app(URL).conf.task_track_started is True


def test_explicit_url_is_used_for_broker_and_result_backend() -> None:
    app = create_celery_app(URL)
    assert app.conf.broker_url == URL
    assert app.conf.result_backend == URL


def test_url_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", URL)
    app = create_celery_app()
    assert app.conf.broker_url == URL
    assert app.conf.result_backend == URL


def test_default_url_points_to_local_redis() -> None:
    assert RedisSettings(_env_file=None).redis_url == "redis://localhost:6379/0"  # type: ignore[call-arg]


@pytest.mark.parametrize("bad", ["http://localhost:6379", "localhost:6379", ""])
def test_non_redis_url_is_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        RedisSettings(redis_url=bad, _env_file=None)  # type: ignore[call-arg]


def test_rediss_scheme_is_accepted() -> None:
    assert RedisSettings(redis_url="rediss://host:6379/0", _env_file=None).redis_url.startswith(  # type: ignore[call-arg]
        "rediss://"
    )


def test_tasks_run_eagerly_for_unit_tests() -> None:
    app = create_celery_app(URL)
    app.conf.task_always_eager = True

    @app.task
    def add(x: int, y: int) -> int:
        return x + y

    assert add.delay(2, 3).get() == 5
