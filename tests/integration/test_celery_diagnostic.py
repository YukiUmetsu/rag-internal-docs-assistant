from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from src.backend.app.main import app


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def require_celery_env() -> None:
    if not os.getenv("REDIS_URL") or not os.getenv("CELERY_BROKER_URL"):
        pytest.skip("REDIS_URL and CELERY_BROKER_URL must be configured for celery integration tests")


def test_health_reports_redis_and_worker_availability() -> None:
    deadline = time.monotonic() + 60
    last_response = None

    while time.monotonic() < deadline:
        response = client.get("/api/health")
        last_response = response
        body = response.json()
        if body["redis_available"] and body["celery_worker_available"]:
            break
        time.sleep(1)

    assert last_response is not None
    assert last_response.status_code == 200
    body = last_response.json()
    assert body["redis_available"] is True
    assert body["celery_worker_available"] is True


def test_celery_diagnostic_task_round_trip() -> None:
    submission_response = client.post(
        "/api/diagnostics/celery/ping",
        json={"message": "hello"},
    )
    assert submission_response.status_code == 202
    task_id = submission_response.json()["task_id"]

    deadline = time.monotonic() + 60
    status_response = None
    while time.monotonic() < deadline:
        status_response = client.get(f"/api/diagnostics/celery/{task_id}")
        status_body = status_response.json()
        if status_body["state"] in {"SUCCESS", "FAILURE"}:
            break
        time.sleep(1)

    assert status_response is not None
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["state"] == "SUCCESS"
    assert status_body["ready"] is True
    assert status_body["result"]["message"] == "hello"
    assert status_body["result"]["status"] == "ok"
