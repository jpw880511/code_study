from typing import Any, NoReturn

import pytest
from src.api.exceptions import DOMAIN_ERROR_STATUS
from src.tasks import document_generation
from src.tasks.celery_app import TASK_TIME_LIMIT_SECONDS, celery_app, create_celery_app
from src.tasks.document_generation import (
    COMPLETED,
    DEFER_SECONDS,
    DEFERRED,
    enqueue_generation,
    generate_document,
)

REAL_ENQUEUE = enqueue_generation  # imported before the autouse fake replaces the module's name


def test_the_job_has_its_own_longer_limits_and_safe_redelivery() -> None:
    assert generate_document.name == "document_generation.generate"
    assert generate_document.queue == "document_generation"
    assert generate_document.soft_time_limit == 540
    assert generate_document.time_limit == 600
    assert generate_document.acks_late is True
    assert generate_document.reject_on_worker_lost is True
    # the global limit of the other jobs is unchanged
    assert TASK_TIME_LIMIT_SECONDS == 300
    assert celery_app.conf.task_time_limit == 300
    # a stale document (15 minutes) is judged after the hard limit
    from src.services.document.document_queue_service import STALE_AFTER

    assert STALE_AFTER.total_seconds() > generate_document.time_limit


def test_the_worker_imports_the_job_module_by_itself() -> None:
    assert "src.tasks.document_generation" in create_celery_app("redis://h:1/0").conf.include


def test_a_finished_job_returns_its_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(document_generation, "run_generate_document", lambda task_id: COMPLETED)
    assert generate_document.run("some-task") == COMPLETED


def test_a_deferred_job_asks_celery_to_try_again_later(monkeypatch: pytest.MonkeyPatch) -> None:
    class Retried(Exception):
        pass

    calls: list[dict[str, Any]] = []

    def fake_retry(**options: Any) -> NoReturn:
        calls.append(options)
        raise Retried

    monkeypatch.setattr(document_generation, "run_generate_document", lambda task_id: DEFERRED)
    monkeypatch.setattr(generate_document, "retry", fake_retry)
    with pytest.raises(Retried):
        generate_document.run("some-task")
    assert calls == [{"countdown": DEFER_SECONDS, "max_retries": None}]
    assert DEFER_SECONDS == 15


def test_enqueue_sends_the_job_under_its_prepared_id(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(generate_document, "apply_async", lambda **options: sent.append(options))
    REAL_ENQUEUE("task-1", "job-1")
    assert len(sent) == 1
    assert sent[0]["args"] == ["task-1"]
    assert sent[0]["task_id"] == "job-1"
    assert sent[0]["queue"] == "document_generation"
    assert sent[0]["retry_policy"]["max_retries"] <= 2  # a dead broker must not hold the request


def test_the_broker_connection_gives_up_quickly() -> None:
    options = celery_app.conf.broker_transport_options
    assert 0 < options["socket_connect_timeout"] <= 5


def test_document_not_found_is_a_404() -> None:
    assert DOMAIN_ERROR_STATUS["document_not_found"] == 404


def test_tests_never_reach_a_broker_unless_they_patch_apply_async() -> None:
    assert document_generation.enqueue_generation is not REAL_ENQUEUE  # replaced by conftest
