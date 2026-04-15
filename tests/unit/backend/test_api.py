from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from src.backend.app.main import app
from src.backend.app.core.queue import CeleryWorkerHealth, DiagnosticTaskStatus, RedisHealth
from src.backend.app.core.ingest_jobs import IngestJobDetail, IngestJobSummary
from src.backend.app.core.uploads import UploadedFileSummary as UploadedFileRecord
from src.backend.app.schemas.chat import ChatResponse
from src.backend.app.schemas.retrieval import RetrievalMetadata
from src.backend.app.services import rag_service


client = TestClient(app)


def make_doc(file_name: str = "refund_policy_2025.md") -> Document:
    return Document(
        page_content="Refunds were allowed within 14 days in 2025.",
        metadata={
            "file_name": file_name,
            "domain": "policies",
            "topic": "refund_policy",
            "year": "2025",
        },
    )


def test_health_endpoint_returns_status() -> None:
    with (
        patch("src.backend.app.api.routes.check_redis_health", return_value=RedisHealth(available=True)),
        patch(
            "src.backend.app.api.routes.check_celery_worker_health",
            return_value=CeleryWorkerHealth(available=True),
        ),
    ):
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "vectorstore_available" in body
    assert "chunks_available" in body
    assert "redis_available" in body
    assert "celery_worker_available" in body
    assert "live_llm_configured" in body


def test_retrieve_endpoint_serializes_sources() -> None:
    with patch.object(rag_service, "retrieve", return_value=[make_doc()]):
        response = client.post(
            "/api/retrieve",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "retrieve_only",
                "final_k": 4,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode_used"] == "retrieve_only"
    assert body["sources"][0]["file_name"] == "refund_policy_2025.md"
    assert body["retrieval"]["detected_year"] == "2025"


def test_retrieve_endpoint_still_succeeds_when_history_persistence_fails() -> None:
    with (
        patch.object(rag_service, "retrieve", return_value=[make_doc()]),
        patch.object(rag_service, "persist_search_history", side_effect=RuntimeError("db down")),
    ):
        response = client.post(
            "/api/retrieve",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "retrieve_only",
                "final_k": 4,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["sources"][0]["file_name"] == "refund_policy_2025.md"


def test_chat_endpoint_supports_mock_mode() -> None:
    with patch.object(rag_service, "retrieve", return_value=[make_doc()]):
        response = client.post(
            "/api/chat",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "mock",
                "final_k": 4,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode_used"] == "mock"
    assert "Mock answer" in body["answer"]
    assert body["sources"][0]["year"] == "2025"


def test_chat_endpoint_falls_back_when_live_generation_fails() -> None:
    with (
        patch.object(rag_service, "retrieve", return_value=[make_doc()]),
        patch.object(rag_service, "generate_answer_from_docs", side_effect=RuntimeError("quota")),
    ):
        response = client.post(
            "/api/chat",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "live",
                "final_k": 4,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode_used"] == "mock_fallback"
    assert "Live answer generation failed" in body["warning"]
    assert "Mock answer" in body["answer"]


def test_chat_response_schema_allows_retrieve_only_mode() -> None:
    response = ChatResponse(
        answer="Retrieved sources are ready.",
        sources=[],
        retrieval=RetrievalMetadata(
            use_hybrid=True,
            use_rerank=True,
            detected_year=None,
            final_k=4,
            initial_k=12,
        ),
        mode_used="retrieve_only",
        latency_ms=1,
    )

    assert response.mode_used == "retrieve_only"


def test_celery_ping_endpoint_enqueues_task() -> None:
    with patch("src.backend.app.api.routes.enqueue_diagnostic_task", return_value="task-123"):
        response = client.post(
            "/api/diagnostics/celery/ping",
            json={"message": "ping"},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["task_id"] == "task-123"
    assert body["state"] == "PENDING"


def test_celery_ping_status_endpoint_serializes_task_state() -> None:
    with patch(
        "src.backend.app.api.routes.get_diagnostic_task_status",
        return_value=DiagnosticTaskStatus(
            task_id="task-123",
            state="SUCCESS",
            ready=True,
            result={"message": "pong", "status": "ok"},
            traceback=None,
        ),
    ):
        response = client.get("/api/diagnostics/celery/task-123")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-123"
    assert body["state"] == "SUCCESS"
    assert body["result"]["status"] == "ok"


def test_ingest_job_creation_endpoint_serializes_job() -> None:
    with patch(
        "src.backend.app.api.routes.enqueue_validation_ingest_job",
        return_value=IngestJobDetail(
            id="job-123",
            task_id="job-123",
            source_type="mounted_data",
            job_mode="validation",
            status="queued",
            requested_paths=["data"],
            uploaded_file_ids=[],
            result_message=None,
            error_message=None,
            created_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            updated_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            started_at=None,
            finished_at=None,
        ),
    ):
        response = client.post(
            "/api/ingest/jobs",
            json={"source_type": "mounted_data", "job_mode": "validation", "requested_paths": ["data"]},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["id"] == "job-123"
    assert body["status"] == "queued"


def test_ingest_jobs_list_endpoint_serializes_jobs() -> None:
    with patch(
        "src.backend.app.api.routes.list_ingest_jobs",
        return_value=[
            IngestJobSummary(
                id="job-123",
                task_id="job-123",
                source_type="mounted_data",
                job_mode="validation",
                status="queued",
                requested_paths=["data"],
                uploaded_file_ids=[],
                result_message=None,
                error_message=None,
                created_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                updated_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            )
        ],
    ):
        response = client.get("/api/ingest/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["status"] == "queued"


def test_ingest_job_detail_endpoint_serializes_job() -> None:
    with patch(
        "src.backend.app.api.routes.get_ingest_job",
        return_value=IngestJobDetail(
            id="job-123",
            task_id="job-123",
            source_type="mounted_data",
            job_mode="validation",
            status="succeeded",
            requested_paths=["data"],
            uploaded_file_ids=[],
            result_message="Validated 1 requested path(s) and 0 uploaded file(s).",
            error_message=None,
            created_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            updated_at=datetime.fromisoformat("2026-04-15T12:00:01+00:00"),
            started_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            finished_at=datetime.fromisoformat("2026-04-15T12:00:01+00:00"),
        ),
    ):
        response = client.get("/api/ingest/jobs/job-123")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"


def test_upload_endpoint_serializes_uploaded_files() -> None:
    with patch(
        "src.backend.app.api.routes.store_uploaded_files",
        return_value=[
            UploadedFileRecord(
                id="upload-123",
                original_filename="notes.md",
                stored_path="artifacts/uploads/upload-123_notes.md",
                content_type="text/markdown",
                file_size_bytes=12,
                checksum="abc123",
                created_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                updated_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            )
        ],
    ):
        response = client.post(
            "/api/ingest/uploads",
            files=[("files", ("notes.md", b"# Notes\n", "text/markdown"))],
        )

    assert response.status_code == 201
    body = response.json()
    assert body[0]["original_filename"] == "notes.md"
    assert body[0]["file_size_bytes"] == 12


def test_upload_endpoint_rejects_unsupported_file_types() -> None:
    response = client.post(
        "/api/ingest/uploads",
        files=[("files", ("notes.txt", b"plain text", "text/plain"))],
    )

    assert response.status_code == 400
    assert "Unsupported upload file type" in response.json()["detail"]
