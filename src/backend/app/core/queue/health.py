from __future__ import annotations

from dataclasses import dataclass

from src.backend.app.core.queue.app import celery_app

try:  # pragma: no cover - optional dependency fallback
    from redis import Redis
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - exercised when Redis is unavailable
    Redis = None  # type: ignore[assignment]

    class RedisError(Exception):
        pass


@dataclass(frozen=True)
class RedisHealth:
    available: bool
    error: str | None = None


@dataclass(frozen=True)
class CeleryWorkerHealth:
    available: bool
    error: str | None = None


def check_redis_health(redis_url: str | None) -> RedisHealth:
    if not redis_url:
        return RedisHealth(available=False, error="REDIS_URL is not configured")
    if Redis is None:
        return RedisHealth(available=False, error="Redis is not installed")

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
