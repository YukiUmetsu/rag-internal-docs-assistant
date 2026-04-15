from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from celery import Celery
from celery.result import AsyncResult
from redis import Redis
from redis.exceptions import RedisError

from src.backend.app.core.settings import get_settings


@dataclass(frozen=True)
class RedisHealth:
    available: bool
    error: str | None = None


@dataclass(frozen=True)
class CeleryWorkerHealth:
    available: bool
    error: str | None = None


@dataclass(frozen=True)
class DiagnosticTaskStatus:
    task_id: str
    state: str
    ready: bool
    result: dict[str, Any] | str | None
    traceback: str | None = None


def create_celery_app() -> Celery:
    settings = get_settings()
    broker_url = settings.celery_broker_url or settings.redis_url or "redis://redis:6379/0"
    result_backend = settings.celery_result_backend or settings.redis_url or "redis://redis:6379/1"
    app = Celery("acme_company_assistant", broker=broker_url, backend=result_backend)
    app.conf.update(
        accept_content=["json"],
        broker_connection_retry_on_startup=True,
        enable_utc=True,
        result_serializer="json",
        task_serializer="json",
        task_track_started=True,
        timezone="UTC",
    )
    return app


celery_app = create_celery_app()


@celery_app.task(name="diagnostics.ping")
def diagnostic_ping(message: str = "pong") -> dict[str, str]:
    return {
        "message": message,
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def enqueue_diagnostic_task(message: str = "pong") -> str:
    result = diagnostic_ping.delay(message)
    return result.id


def get_diagnostic_task_status(task_id: str) -> DiagnosticTaskStatus:
    result = AsyncResult(task_id, app=celery_app)
    payload = result.result if result.ready() else None
    if isinstance(payload, BaseException):
        payload = str(payload)
    return DiagnosticTaskStatus(
        task_id=task_id,
        state=result.state,
        ready=result.ready(),
        result=payload,
        traceback=result.traceback,
    )


def check_redis_health(redis_url: str | None) -> RedisHealth:
    if not redis_url:
        return RedisHealth(available=False, error="REDIS_URL is not configured")

    try:
        client = Redis.from_url(
            redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
    except RedisError as exc:
        return RedisHealth(available=False, error=f"{type(exc).__name__}: {exc}")

    return RedisHealth(available=True)


def check_celery_worker_health() -> CeleryWorkerHealth:
    try:
        inspector = celery_app.control.inspect(timeout=1)
        if inspector is None:
            return CeleryWorkerHealth(available=False, error="No Celery workers responded")
        ping_response = inspector.ping()
    except Exception as exc:  # pragma: no cover - transport and broker failures
        return CeleryWorkerHealth(available=False, error=f"{type(exc).__name__}: {exc}")

    if not ping_response:
        return CeleryWorkerHealth(available=False, error="No Celery workers responded")

    return CeleryWorkerHealth(available=True)
