from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from src.backend.app.main import app


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def ensure_ingest_schema() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for ingest job integration tests")

    alembic_ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(alembic_ini_path))
    command.upgrade(config, "head")


def test_ingest_job_success_lifecycle() -> None:
    response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "validation",
            "requested_paths": [
                "data/policies/refund_policy_2025.md",
                "data/engineering/payment_flow.md",
            ],
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"

    job_id = body["id"]
    observed_states = {body["status"]}
    deadline = time.monotonic() + 30
    latest = body

    while time.monotonic() < deadline:
        latest_response = client.get(f"/api/ingest/jobs/{job_id}")
        assert latest_response.status_code == 200
        latest = latest_response.json()
        observed_states.add(latest["status"])
        if latest["status"] == "succeeded":
            break
        time.sleep(0.2)

    assert latest["status"] == "succeeded"
    assert latest["result_message"] == "Validated 2 requested path(s) and 0 uploaded file(s)."
    assert "running" in observed_states
    assert "queued" in observed_states

    list_response = client.get("/api/ingest/jobs", params={"limit": 5})
    assert list_response.status_code == 200
    jobs = list_response.json()
    assert any(job["id"] == job_id for job in jobs)


def test_ingest_job_failure_lifecycle() -> None:
    response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "validation",
            "requested_paths": ["data/does-not-exist.md"],
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"

    job_id = body["id"]
    deadline = time.monotonic() + 30
    latest = body

    while time.monotonic() < deadline:
        latest_response = client.get(f"/api/ingest/jobs/{job_id}")
        assert latest_response.status_code == 200
        latest = latest_response.json()
        if latest["status"] == "failed":
            break
        time.sleep(0.2)

    assert latest["status"] == "failed"
    assert "Missing requested paths" in latest["error_message"]
