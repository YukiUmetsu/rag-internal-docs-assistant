from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.backend.app.core.settings import get_settings

try:  # pragma: no cover - optional dependency fallback
    from celery import Celery
except ImportError:  # pragma: no cover - exercised when Celery is unavailable
    Celery = None  # type: ignore[assignment]


class _FallbackTask:
    def __init__(self, func):
        self._func = func

    def __call__(self, *args: Any, **kwargs: Any):
        return self._func(*args, **kwargs)

    def delay(self, *_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("Celery is not installed")

    def apply_async(self, *_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("Celery is not installed")


class _FallbackControl:
    def inspect(self, timeout: int = 1) -> None:
        return None


class _FallbackCeleryApp:
    control = _FallbackControl()

    def task(self, *args: Any, **kwargs: Any):
        def decorator(func):
            return _FallbackTask(func)

        return decorator


def create_celery_app() -> Celery:
    if Celery is None:
        raise RuntimeError("Celery is not installed")
    settings = get_settings()
    broker_url = settings.celery_broker_url or settings.redis_url or "redis://redis:6379/0"
    result_backend = settings.celery_result_backend or settings.redis_url or "redis://redis:6379/1"
    app = Celery(
        "acme_company_assistant",
        broker=broker_url,
        backend=result_backend,
        include=["src.backend.app.core.ingest_jobs"],
    )
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


celery_app = create_celery_app() if Celery is not None else _FallbackCeleryApp()


@celery_app.task(name="diagnostics.ping")
def diagnostic_ping(message: str = "pong") -> dict[str, str]:
    return {
        "message": message,
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
