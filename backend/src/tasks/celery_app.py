from pathlib import Path

from celery import Celery
from kombu import Exchange, Queue
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

QUEUE_NAMES = ("default", "document_generation", "practice_generation", "cleanup")
TASK_TIME_LIMIT_SECONDS = 300
# Jobs the worker must know without being told: it only imports this module by itself.
TASK_MODULES = ["src.tasks.document_generation"]
# A dead broker must fail a publish quickly instead of holding the caller for a minute.
BROKER_CONNECT_TIMEOUT_SECONDS = 3


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", extra="ignore", populate_by_name=True
    )

    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    @field_validator("redis_url")
    @classmethod
    def require_redis_scheme(cls, url: str) -> str:
        if not url.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return url


def create_celery_app(redis_url: str | None = None) -> Celery:
    url = redis_url or RedisSettings().redis_url
    app = Celery("code_study", broker=url, backend=url, include=TASK_MODULES)
    app.conf.update(
        task_queues=tuple(
            Queue(name, Exchange(name, type="direct"), routing_key=name) for name in QUEUE_NAMES
        ),
        task_default_queue="default",
        task_time_limit=TASK_TIME_LIMIT_SECONDS,
        task_track_started=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"socket_connect_timeout": BROKER_CONNECT_TIMEOUT_SECONDS},
    )
    return app


celery_app = create_celery_app()
