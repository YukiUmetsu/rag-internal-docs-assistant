from __future__ import annotations

from src.backend.app.core.queue import (
    CeleryWorkerHealth,
    DiagnosticTaskStatus,
    RedisHealth,
    celery_app,
    check_celery_worker_health,
    check_redis_health,
    enqueue_diagnostic_task,
    get_diagnostic_task_status,
)


def test_queue_package_re_exports_public_symbols() -> None:
    assert celery_app is not None
    assert callable(check_celery_worker_health)
    assert callable(check_redis_health)
    assert callable(enqueue_diagnostic_task)
    assert callable(get_diagnostic_task_status)
    assert RedisHealth(available=True).available is True
    assert CeleryWorkerHealth(available=True).available is True
    assert DiagnosticTaskStatus(
        task_id="task-123",
        state="SUCCESS",
        ready=True,
        result=None,
    ).task_id == "task-123"
