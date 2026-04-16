from __future__ import annotations

import os
import time
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from src.backend.app.core.corpus import (
    count_corpus_rows_for_job,
    count_source_document_versions,
)
from src.backend.app.main import app


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def ensure_corpus_schema() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for corpus ingestion integration tests")

    alembic_ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(alembic_ini_path))
    command.upgrade(config, "head")


def _wait_for_ingest_job(job_id: str, *, timeout_seconds: float = 120.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, object] | None = None

    while time.monotonic() < deadline:
        response = client.get(f"/api/ingest/jobs/{job_id}")
        assert response.status_code == 200
        latest = response.json()
        if latest["status"] in {"succeeded", "failed"}:
            return latest
        time.sleep(0.5)

    raise AssertionError(f"Ingest job {job_id} did not finish in time: {latest}")


def test_full_document_ingest_persists_source_documents_and_chunks(
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

    latest = _wait_for_ingest_job(job_id)
    assert latest["status"] == "succeeded"
    assert "Ingested" in latest["result_message"]

    database_url = os.environ["DATABASE_URL"]
    counts = count_corpus_rows_for_job(database_url, ingest_job_id=job_id)
    assert counts["source_documents_count"] == len(basic_ingest_fixture_paths)
    assert counts["document_chunks_count"] > 0


def test_upload_ingest_persists_uploaded_files(tmp_path: Path) -> None:
    upload_path = tmp_path / "upload_note.md"
    upload_path.write_text(
        "# Upload Note\n\nThis document was uploaded for ingestion testing.",
        encoding="utf-8",
    )

    with upload_path.open("rb") as handle:
        response = client.post(
            "/api/ingest/uploads",
            files=[("files", ("upload_note.md", handle, "text/markdown"))],
        )

    assert response.status_code == 201
    upload_id = response.json()[0]["id"]

    response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "uploaded_files",
            "job_mode": "partial",
            "requested_paths": [],
            "uploaded_file_ids": [upload_id],
        },
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    latest = _wait_for_ingest_job(job_id)
    assert latest["status"] == "succeeded"

    database_url = os.environ["DATABASE_URL"]
    counts = count_corpus_rows_for_job(database_url, ingest_job_id=job_id)
    assert counts["source_documents_count"] == 1
    assert counts["document_chunks_count"] > 0


def test_partial_document_ingest_replaces_changed_source(project_root: Path) -> None:
    corpus_dir = project_root / "artifacts" / "test_ingest"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    source_file = corpus_dir / f"partial_policy_{uuid4().hex}.md"

    source_file.write_text(
        "# Partial Policy\n\nVersion 1 of the policy text.",
        encoding="utf-8",
    )

    first_response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "partial",
            "requested_paths": [str(source_file)],
            "uploaded_file_ids": [],
        },
    )
    assert first_response.status_code == 202
    first_job_id = first_response.json()["id"]
    assert _wait_for_ingest_job(first_job_id)["status"] == "succeeded"

    database_url = os.environ["DATABASE_URL"]
    first_counts = count_source_document_versions(
        database_url,
        source_path=str(source_file.resolve()),
    )
    assert first_counts == {"total_count": 1, "active_count": 1}

    source_file.write_text(
        "# Partial Policy\n\nVersion 2 of the policy text with a meaningful change.",
        encoding="utf-8",
    )

    second_response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "partial",
            "requested_paths": [str(source_file)],
            "uploaded_file_ids": [],
        },
    )
    assert second_response.status_code == 202
    second_job_id = second_response.json()["id"]
    assert _wait_for_ingest_job(second_job_id)["status"] == "succeeded"

    second_counts = count_source_document_versions(
        database_url,
        source_path=str(source_file.resolve()),
    )
    assert second_counts == {"total_count": 2, "active_count": 1}
