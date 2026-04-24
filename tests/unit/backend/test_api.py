from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import ANY, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from src.backend.app.main import app
from src.backend.app.core.admin import (
    AdminCorpusStatus,
    AdminDashboardSnapshot,
    AdminHealthFlag,
    AdminJobStat,
    AdminMetric,
    AdminQuestionStat,
    AdminRetrieverBackendState,
    AdminSeriesPoint,
    AdminUploadStat,
)
from src.backend.app.core.queue.health import CeleryWorkerHealth, RedisHealth
from src.backend.app.core.queue.tasks import DiagnosticTaskStatus
from src.backend.app.core.ingest_jobs import IngestJobDetail, IngestJobSummary
from src.backend.app.core.feedback import FeedbackDetail as FeedbackDetailRecord
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
        patch("src.backend.app.core.queue.health.check_redis_health", return_value=RedisHealth(available=True)),
        patch(
            "src.backend.app.core.queue.health.check_celery_worker_health",
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
    with (
        patch("src.backend.app.core.request_ids.generate_request_id", return_value="request-123"),
        patch.object(rag_service, "retrieve", return_value=[make_doc()]),
        patch.object(rag_service, "persist_search_history", return_value="request-123"),
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
    assert body["request_id"] == "request-123"
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
    assert body["request_id"] is None
    assert body["sources"][0]["file_name"] == "refund_policy_2025.md"
    assert "feedback is unavailable" in body["warning"]


def test_retrieve_endpoint_omits_request_id_when_history_write_returns_none() -> None:
    with (
        patch("src.backend.app.core.request_ids.generate_request_id", return_value="request-789"),
        patch.object(rag_service, "retrieve", return_value=[make_doc()]),
        patch.object(rag_service, "persist_search_history", return_value=None),
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
    assert body["request_id"] is None
    assert "feedback is unavailable" in body["warning"]


def test_chat_endpoint_supports_mock_mode() -> None:
    with (
        patch("src.backend.app.core.request_ids.generate_request_id", return_value="request-456"),
        patch.object(rag_service, "retrieve", return_value=[make_doc()]),
        patch.object(rag_service, "persist_search_history", return_value="request-456"),
    ):
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
    assert body["request_id"] == "request-456"
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


def test_chat_endpoint_omits_request_id_when_history_persistence_fails() -> None:
    with (
        patch.object(rag_service, "retrieve", return_value=[make_doc()]),
        patch.object(rag_service, "persist_search_history", side_effect=RuntimeError("db down")),
    ):
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
    assert body["request_id"] is None
    assert "feedback is unavailable" in body["warning"]


def test_chat_endpoint_omits_request_id_when_history_write_returns_none() -> None:
    with (
        patch.object(rag_service, "retrieve", return_value=[make_doc()]),
        patch.object(rag_service, "persist_search_history", return_value=None),
    ):
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
    assert body["request_id"] is None
    assert "feedback is unavailable" in body["warning"]


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


def test_retrieve_context_trace_input_summary_includes_request_id() -> None:
    summary = rag_service.summarize_retrieve_context_inputs(
        {
            "question": "What was the refund window in 2025?",
            "final_k": 5,
            "request_id": "request-123",
            "langsmith_extra": {"run_id": "request-123"},
        }
    )

    assert summary == {
        "question": "What was the refund window in 2025?",
        "question_chars": 35,
        "final_k": 5,
        "request_id": "request-123",
        "langsmith_extra": {"run_id": "request-123"},
    }


def test_feedback_endpoint_serializes_submission() -> None:
    feedback_record = FeedbackDetailRecord(
        id="feedback-123",
        search_query_id="request-123",
        request_kind="chat",
        question="What was the refund window in 2025?",
        verdict="not_helpful",
        reason_code="grounding",
        issue_category="grounding",
        review_status="new",
        comment_preview="Too vague",
        created_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
        reviewed_at=None,
        comment="Too vague",
        reviewed_by=None,
        promoted_eval_path=None,
        langsmith_run_id="request-123",
    )
    with (
        patch("src.backend.app.core.feedback.persist_answer_feedback", return_value=feedback_record),
    ):
        response = client.post(
            "/api/feedback",
            json={
                "search_query_id": "request-123",
                "verdict": "not_helpful",
                "reason_code": "grounding",
                "comment": "Too vague",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "feedback-123"
    assert body["search_query_id"] == "request-123"
    assert body["reason_code"] == "grounding"


def test_admin_feedback_update_logs_missing_row(caplog) -> None:
    with (
        patch("src.backend.app.core.feedback.update_answer_feedback_review", side_effect=KeyError("feedback-123")),
        caplog.at_level(logging.WARNING, logger="src.backend.app.api.admin_routes"),
    ):
        response = client.patch(
            "/api/admin/feedback/feedback-123",
            json={
                "review_status": "triaged",
                "reviewed_by": "reviewer@example.com",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Feedback entry not found"
    assert "endpoint=update_admin_feedback" in caplog.text
    assert "feedback_id=feedback-123" in caplog.text
    assert "review_status=triaged" in caplog.text
    assert "reviewed_by=reviewer@example.com" in caplog.text


def test_admin_feedback_update_logs_runtime_failure(caplog) -> None:
    with (
        patch(
            "src.backend.app.core.feedback.update_answer_feedback_review",
            side_effect=RuntimeError("db unavailable"),
        ),
        caplog.at_level(logging.WARNING, logger="src.backend.app.api.admin_routes"),
    ):
        response = client.patch(
            "/api/admin/feedback/feedback-123",
            json={
                "review_status": "triaged",
                "reviewed_by": "reviewer@example.com",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "db unavailable"
    assert "endpoint=update_admin_feedback" in caplog.text
    assert "feedback_id=feedback-123" in caplog.text
    assert "db unavailable" in caplog.text


def test_admin_feedback_update_rejects_invalid_transition(caplog) -> None:
    with (
        patch(
            "src.backend.app.core.feedback.update_answer_feedback_review",
            side_effect=ValueError("Cannot transition feedback review status from promoted to promoted"),
        ),
        caplog.at_level(logging.WARNING, logger="src.backend.app.api.admin_routes"),
    ):
        response = client.patch(
            "/api/admin/feedback/feedback-123",
            json={
                "review_status": "promoted",
                "reviewed_by": "reviewer@example.com",
            },
        )

    assert response.status_code == 409
    assert "promoted to promoted" in response.json()["detail"]
    assert "endpoint=update_admin_feedback" in caplog.text


def test_celery_ping_endpoint_enqueues_task() -> None:
    with patch("src.backend.app.core.queue.tasks.enqueue_diagnostic_task", return_value="task-123"):
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
        "src.backend.app.core.queue.tasks.get_diagnostic_task_status",
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
        "src.backend.app.core.ingest_jobs.enqueue_validation_ingest_job",
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
        "src.backend.app.core.ingest_jobs.list_ingest_jobs",
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
        "src.backend.app.core.ingest_jobs.get_ingest_job",
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


def test_admin_dashboard_endpoint_serializes_snapshot() -> None:
    snapshot = AdminDashboardSnapshot(
        retriever_backend="postgres",
        corpus=AdminCorpusStatus(
            status="healthy",
            active_documents=12,
            active_chunks=64,
            orphan_chunks=0,
            documents_without_chunks=0,
            documents_with_missing_files=0,
        ),
        metrics=[
            AdminMetric(label="Active documents", value="12", detail="No new documents in the last 7 days"),
        ],
        search_volume=[AdminSeriesPoint(label="Mon", value=2.0)],
        latency_series=[AdminSeriesPoint(label="Mon", value=1.8)],
        ingest_series=[AdminSeriesPoint(label="Mon", value=1.0)],
        top_questions_week=[
            AdminQuestionStat(
                question="What is the refund window in 2026?",
                count=4,
                last_asked_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                avg_latency_ms=1820.0,
            )
        ],
        top_questions_month=[],
        recent_jobs=[
            AdminJobStat(
                id="job-123",
                source_type="mounted_data",
                job_mode="full",
                status="succeeded",
                summary="Ingested 2 documents",
                started_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                finished_at=datetime.fromisoformat("2026-04-15T12:01:00+00:00"),
                source_documents=2,
                chunks=8,
                task_id="job-123",
            )
        ],
        recent_uploads=[
            AdminUploadStat(
                id="upload-1",
                filename="team-handbook.pdf",
                size_bytes=1024,
                checksum="abc123",
                job_id="job-123",
                created_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            )
        ],
        health_flags=[AdminHealthFlag(label="Failed jobs", value="0")],
        latest_query="What is the refund window in 2026?",
        latest_ingest_at=datetime.fromisoformat("2026-04-15T12:01:00+00:00"),
        latest_failed_ingest_at=None,
    )
    with patch("src.backend.app.core.admin.get_admin_dashboard", return_value=snapshot):
        response = client.get("/api/admin/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["retriever_backend"] == "postgres"
    assert body["corpus"]["status"] == "healthy"
    assert body["metrics"][0]["label"] == "Active documents"
    assert body["recent_jobs"][0]["id"] == "job-123"
    assert body["recent_uploads"][0]["filename"] == "team-handbook.pdf"


def test_admin_retriever_backend_endpoint_serializes_state() -> None:
    with patch(
        "src.backend.app.core.admin.get_admin_retriever_backend",
        return_value=AdminRetrieverBackendState(retriever_backend="postgres", override_enabled=True),
    ):
        response = client.get("/api/admin/retriever-backend")

    assert response.status_code == 200
    body = response.json()
    assert body["retriever_backend"] == "postgres"
    assert body["override_enabled"] is True


def test_admin_retriever_backend_update_endpoint_serializes_state() -> None:
    with patch(
        "src.backend.app.core.admin.set_admin_retriever_backend",
        return_value=AdminRetrieverBackendState(retriever_backend="faiss", override_enabled=True),
    ):
        response = client.post(
            "/api/admin/retriever-backend",
            json={"retriever_backend": "faiss"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["retriever_backend"] == "faiss"
    assert body["override_enabled"] is True


def test_admin_uploads_endpoint_serializes_paged_uploads() -> None:
    with patch(
        "src.backend.app.core.admin.list_admin_uploads",
        return_value=(
            [
                AdminUploadStat(
                    id="upload-1",
                    filename="team-handbook.pdf",
                    size_bytes=1024,
                    checksum="abc123",
                    job_id="job-123",
                    created_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                )
            ],
            1,
        ),
    ) as mock_list:
        response = client.get("/api/admin/uploads?limit=5&offset=10&sort_by=filename&sort_dir=asc")

    assert response.status_code == 200
    mock_list.assert_called_once_with(ANY, limit=5, offset=10, sort_by="filename", sort_dir="asc")
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["job_id"] == "job-123"


def test_admin_jobs_endpoint_serializes_paged_jobs() -> None:
    with patch(
        "src.backend.app.core.admin.list_admin_jobs",
        return_value=(
            [
                AdminJobStat(
                    id="job-123",
                    source_type="mounted_data",
                    job_mode="full",
                    status="succeeded",
                    summary="Ingested 2 documents",
                    started_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                    finished_at=datetime.fromisoformat("2026-04-15T12:01:00+00:00"),
                    source_documents=2,
                    chunks=8,
                    task_id="job-123",
                )
            ],
            1,
        ),
    ) as mock_list:
        response = client.get("/api/admin/jobs?limit=7&offset=2&sort_by=status&sort_dir=asc")

    assert response.status_code == 200
    mock_list.assert_called_once_with(
        ANY,
        limit=7,
        offset=2,
        sort_by="status",
        sort_dir="asc",
        days=None,
    )
    body = response.json()
    assert body["items"][0]["source_documents"] == 2
    assert body["items"][0]["chunks"] == 8


def test_admin_documents_endpoint_serializes_paged_documents() -> None:
    from src.backend.app.schemas.documents import SourceDocumentSummary

    with patch(
        "src.backend.app.core.admin.list_admin_documents",
        return_value=(
            [
                SourceDocumentSummary(
                    id="doc-1",
                    source_kind="uploaded_files",
                    display_name="team-handbook.pdf",
                    source_path=None,
                    uploaded_file_id="upload-1",
                    ingest_job_id="job-123",
                    domain="policies",
                    topic="refunds",
                    year=2026,
                    content_type="application/pdf",
                    file_size_bytes=1024,
                    checksum="abc123",
                    is_active=True,
                    chunk_count=3,
                    created_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                    updated_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                    ingested_at=datetime.fromisoformat("2026-04-15T12:01:00+00:00"),
                )
            ],
            1,
        ),
    ):
        response = client.get("/api/admin/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["source_kind"] == "uploaded_files"
    assert body["items"][0]["chunk_count"] == 3


def test_admin_history_endpoint_serializes_paged_history() -> None:
    with patch(
        "src.backend.app.core.admin.list_admin_history",
        return_value=(
            [
                {
                    "id": "query-1",
                    "request_kind": "chat",
                    "question": "What is the refund window in 2026?",
                    "requested_mode": "live",
                    "mode_used": "live",
                    "final_k": 4,
                    "initial_k": 12,
                    "detected_year": "2026",
                    "answer_preview": "Refunds are available for 14 days.",
                    "latency_ms": 1800,
                    "source_count": 3,
                    "unique_source_count": 1,
                    "warning": None,
                    "created_at": datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                }
            ],
            1,
        ),
    ):
        response = client.get("/api/admin/history")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["answer_preview"] == "Refunds are available for 14 days."


def test_upload_endpoint_serializes_uploaded_files() -> None:
    with patch(
        "src.backend.app.core.uploads.store_uploaded_files",
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
