from __future__ import annotations

from uuid import uuid4
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
def ensure_admin_schema() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for admin integration tests")

    alembic_ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(alembic_ini_path))
    command.upgrade(config, "head")


def test_admin_document_and_upload_lists_reflect_recent_ingest() -> None:
    unique_suffix = uuid4().hex
    upload_filename = f"admin-ref-{unique_suffix}.md"
    upload_content = f"# Admin doc {unique_suffix}\n".encode("utf-8")

    upload_response = client.post(
        "/api/ingest/uploads",
        files=[("files", (upload_filename, upload_content, "text/markdown"))],
    )
    assert upload_response.status_code == 201
    upload_id = upload_response.json()[0]["id"]

    job_response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "uploaded_files",
            "job_mode": "full",
            "requested_paths": [],
            "uploaded_file_ids": [upload_id],
        },
    )
    assert job_response.status_code == 202
    job_id = job_response.json()["id"]

    deadline = time.monotonic() + 30
    latest = None
    while time.monotonic() < deadline:
        latest_response = client.get(f"/api/ingest/jobs/{job_id}")
        assert latest_response.status_code == 200
        latest = latest_response.json()
        if latest["status"] == "succeeded":
            break
        time.sleep(0.2)

    assert latest is not None
    assert latest["status"] == "succeeded"

    uploads_response = client.get("/api/admin/uploads?limit=10")
    assert uploads_response.status_code == 200
    uploads_body = uploads_response.json()
    assert uploads_body["total"] >= 1
    assert any(upload["id"] == upload_id and upload["job_id"] == job_id for upload in uploads_body["items"])

    documents_response = client.get("/api/admin/documents?limit=10")
    assert documents_response.status_code == 200
    documents_body = documents_response.json()
    assert documents_body["total"] >= 1
    assert any(document["uploaded_file_id"] == upload_id for document in documents_body["items"])


def test_admin_retriever_backend_switch_updates_live_retrieval(
    basic_ingest_fixture_paths: list[str],
) -> None:
    response = client.post(
        "/api/admin/retriever-backend",
        json={"retriever_backend": "postgres"},
    )
    assert response.status_code == 200
    assert response.json()["retriever_backend"] == "postgres"

    job_response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "full",
            "requested_paths": basic_ingest_fixture_paths,
            "uploaded_file_ids": [],
        },
    )
    assert job_response.status_code == 202
    job_id = job_response.json()["id"]

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        latest_response = client.get(f"/api/ingest/jobs/{job_id}")
        assert latest_response.status_code == 200
        latest = latest_response.json()
        if latest["status"] == "succeeded":
            break
        time.sleep(0.2)
    else:
        raise AssertionError("postgres ingest did not finish in time")

    retrieve_response = client.post(
        "/api/retrieve",
        json={
            "question": "What is the refund window in 2026?",
            "mode": "retrieve_only",
            "final_k": 4,
        },
    )
    assert retrieve_response.status_code == 200
    assert retrieve_response.json()["sources"][0]["file_name"] == "refund_policy_2026.md"

    reset_response = client.post(
        "/api/admin/retriever-backend",
        json={"retriever_backend": "faiss"},
    )
    assert reset_response.status_code == 200


def test_admin_history_endpoint_returns_recent_queries(
    basic_ingest_fixture_paths: list[str],
) -> None:
    switch_response = client.post(
        "/api/admin/retriever-backend",
        json={"retriever_backend": "postgres"},
    )
    assert switch_response.status_code == 200

    job_response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "full",
            "requested_paths": basic_ingest_fixture_paths,
            "uploaded_file_ids": [],
        },
    )
    assert job_response.status_code == 202
    job_id = job_response.json()["id"]

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        latest_response = client.get(f"/api/ingest/jobs/{job_id}")
        assert latest_response.status_code == 200
        latest = latest_response.json()
        if latest["status"] == "succeeded":
            break
        time.sleep(0.2)
    else:
        raise AssertionError("postgres ingest did not finish in time")

    retrieve_response = client.post(
        "/api/retrieve",
        json={
            "question": "What is the refund window in 2026?",
            "mode": "retrieve_only",
            "final_k": 4,
        },
    )
    assert retrieve_response.status_code == 200

    history_response = client.get("/api/admin/history?limit=5&sort_by=created_at&sort_dir=desc")
    assert history_response.status_code == 200
    body = history_response.json()
    assert body["total"] >= 1
    assert body["items"][0]["question"] == "What is the refund window in 2026?"

    reset_response = client.post(
        "/api/admin/retriever-backend",
        json={"retriever_backend": "faiss"},
    )
    assert reset_response.status_code == 200


def test_admin_uploads_endpoint_paginates_and_sorts_uploads() -> None:
    upload_response = client.post(
        "/api/ingest/uploads",
        files=[
            ("files", ("zeta.md", b"# Zeta\n", "text/markdown")),
            ("files", ("alpha.md", b"# Alpha\n", "text/markdown")),
        ],
    )
    assert upload_response.status_code == 201

    first_page_response = client.get(
        "/api/admin/uploads?limit=1&offset=0&sort_by=filename&sort_dir=asc"
    )
    assert first_page_response.status_code == 200
    first_page = first_page_response.json()
    assert first_page["total"] >= 2
    second_page_response = client.get(
        "/api/admin/uploads?limit=1&offset=1&sort_by=filename&sort_dir=asc"
    )
    assert second_page_response.status_code == 200
    second_page = second_page_response.json()
    assert first_page["items"][0]["filename"] <= second_page["items"][0]["filename"]

    assert second_page["total"] == first_page["total"]


def test_admin_jobs_endpoint_paginates_and_sorts_jobs(
    basic_ingest_fixture_paths: list[str],
) -> None:
    validation_response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "validation",
            "requested_paths": basic_ingest_fixture_paths,
            "uploaded_file_ids": [],
        },
    )
    assert validation_response.status_code == 202
    validation_job_id = validation_response.json()["id"]

    full_response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "full",
            "requested_paths": basic_ingest_fixture_paths,
            "uploaded_file_ids": [],
        },
    )
    assert full_response.status_code == 202
    full_job_id = full_response.json()["id"]

    deadline = time.monotonic() + 30
    finished_job_ids: set[str] = set()
    while time.monotonic() < deadline:
        for job_id in (validation_job_id, full_job_id):
            latest_response = client.get(f"/api/ingest/jobs/{job_id}")
            assert latest_response.status_code == 200
            latest = latest_response.json()
            if latest["status"] == "succeeded":
                finished_job_ids.add(job_id)
        if finished_job_ids == {validation_job_id, full_job_id}:
            break
        time.sleep(0.2)
    else:
        raise AssertionError("ingest jobs did not finish in time")

    first_page_response = client.get(
        "/api/admin/jobs?limit=1&offset=0&sort_by=source_documents&sort_dir=desc"
    )
    assert first_page_response.status_code == 200
    first_page = first_page_response.json()
    assert first_page["total"] >= 2
    second_page_response = client.get(
        "/api/admin/jobs?limit=1&offset=1&sort_by=source_documents&sort_dir=desc"
    )
    assert second_page_response.status_code == 200
    second_page = second_page_response.json()
    assert first_page["items"][0]["source_documents"] >= second_page["items"][0]["source_documents"]
    assert second_page["total"] == first_page["total"]
