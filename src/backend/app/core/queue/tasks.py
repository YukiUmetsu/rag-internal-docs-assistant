from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - optional dependency fallback
    from celery.result import AsyncResult
except ImportError:  # pragma: no cover - exercised when Celery is unavailable
    AsyncResult = None  # type: ignore[assignment]

from src.backend.app.core.queue.app import celery_app, diagnostic_ping


@dataclass(frozen=True)
class DiagnosticTaskStatus:
    task_id: str
    state: str
    ready: bool
    result: dict[str, Any] | str | None
    traceback: str | None = None


def enqueue_diagnostic_task(message: str = "pong") -> str:
    if AsyncResult is None:
        raise RuntimeError("Celery is not installed")
    result = diagnostic_ping.delay(message)
    return result.id


def get_diagnostic_task_status(task_id: str) -> DiagnosticTaskStatus:
    if AsyncResult is None:
        raise RuntimeError("Celery is not installed")
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
