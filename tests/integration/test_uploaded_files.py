from __future__ import annotations

import os
import time
from hashlib import sha256
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from src.backend.app.core.settings import Settings
from src.backend.app.main import app


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def ensure_upload_schema() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for upload integration tests")

    alembic_ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(alembic_ini_path))
    command.upgrade(config, "head")


def test_upload_endpoint_persists_file_and_metadata() -> None:
    content = b"# Uploads are handy.\n"
    response = client.post(
        "/api/ingest/uploads",
        files=[("files", ("sample.md", content, "text/markdown"))],
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body) == 1
    uploaded = body[0]
    assert uploaded["original_filename"] == "sample.md"
    assert uploaded["content_type"] == "text/markdown"
    assert uploaded["file_size_bytes"] == len(content)
    assert uploaded["checksum"] == sha256(content).hexdigest()

    stored_path = Path(uploaded["stored_path"])
    assert stored_path.exists()
    assert stored_path.read_bytes() == content

    database_url = os.getenv("DATABASE_URL")
    assert database_url is not None
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    original_filename,
                    stored_path,
                    checksum,
                    file_size_bytes
                FROM uploaded_files
                WHERE id = :upload_id
                """
            ),
            {"upload_id": uploaded["id"]},
        ).mappings().one()

    assert row["original_filename"] == "sample.md"
    assert row["stored_path"] == uploaded["stored_path"]
    assert row["checksum"] == uploaded["checksum"]
    assert row["file_size_bytes"] == len(content)


def test_ingest_job_can_reference_uploaded_files() -> None:
    upload_response = client.post(
        "/api/ingest/uploads",
        files=[("files", ("linked.md", b"# Linked upload\n", "text/markdown"))],
    )
    assert upload_response.status_code == 201
    upload_id = upload_response.json()[0]["id"]

    job_response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "validation",
            "requested_paths": ["data"],
            "uploaded_file_ids": [upload_id],
        },
    )
    assert job_response.status_code == 202
    job = job_response.json()
    assert job["uploaded_file_ids"] == [upload_id]

    deadline = time.monotonic() + 30
    latest = job
    while time.monotonic() < deadline:
        latest_response = client.get(f"/api/ingest/jobs/{job['id']}")
        assert latest_response.status_code == 200
        latest = latest_response.json()
        if latest["status"] == "succeeded":
            break
        time.sleep(0.2)

    assert latest["status"] == "succeeded"
    assert latest["uploaded_file_ids"] == [upload_id]
    assert "uploaded file(s)" in latest["result_message"]


def test_upload_endpoint_is_atomic_for_multi_file_batches(tmp_path: Path) -> None:
    database_url = os.getenv("DATABASE_URL")
    assert database_url is not None

    settings = Settings(
        app_name="test",
        vectorstore_path="artifacts/faiss_index",
        chunks_path="artifacts/chunks.jsonl",
        uploads_path=str(tmp_path),
        max_upload_file_size_bytes=1,
        database_url=database_url,
        redis_url=None,
        celery_broker_url=None,
        celery_result_backend=None,
        groq_model_name=None,
        groq_api_key_present=False,
        langsmith_project=None,
        langsmith_tracing_enabled=False,
        cors_origins=("http://localhost:5173",),
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("src.backend.app.api.routes.get_settings", lambda: settings)
        response = client.post(
            "/api/ingest/uploads",
            files=[
                ("files", ("tiny.md", b"a", "text/markdown")),
                ("files", ("too-large.md", b"bc", "text/markdown")),
            ],
        )

    assert response.status_code == 413
    assert not any(tmp_path.iterdir())

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM uploaded_files
                WHERE original_filename IN ('tiny.md', 'too-large.md')
                """
            )
        ).scalar_one()

    assert count == 0
