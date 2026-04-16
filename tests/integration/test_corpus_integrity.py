from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from src.backend.app.core.corpus import verify_corpus_integrity
from src.backend.app.main import app


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def ensure_corpus_integrity_schema() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for corpus integrity tests")

    alembic_ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(alembic_ini_path))
    command.upgrade(config, "head")


def test_corpus_integrity_is_healthy_after_full_ingest(
    basic_ingest_fixture_paths: list[str],
) -> None:
    response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "full",
            "requested_paths": basic_ingest_fixture_paths,
            "uploaded_file_ids": [],
        },
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    for _ in range(120):
        latest = client.get(f"/api/ingest/jobs/{job_id}")
        assert latest.status_code == 200
        if latest.json()["status"] == "succeeded":
            break
        time.sleep(0.5)
    else:
        pytest.fail("Ingest job did not complete successfully")

    report = verify_corpus_integrity(os.environ["DATABASE_URL"])
    assert report.is_healthy
    assert report.active_source_documents > 0
    assert report.active_document_chunks > 0
    assert report.orphan_chunk_count == 0
    assert report.source_documents_without_chunks == 0
