from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from langchain_core.documents import Document

from src.backend.app.core.admin import (
    AdminCorpusStatus,
    AdminDashboardSnapshot,
    AdminHealthFlag,
    AdminJobStat,
    AdminMetric,
)
from src.backend.app.core.agent_tools import (
    AgentToolContext,
    get_corpus_stats,
    get_recent_ingest_jobs,
    get_recent_searches,
    search_internal_docs,
)
from src.backend.app.core.ingest_jobs import IngestJobSummary
from src.backend.app.schemas.retrieval import RetrievalMetadata
from src.backend.app.services.rag_service import RetrievedContext


def test_search_internal_docs_returns_text_and_sources_for_mocked_retrieval() -> None:
    context = AgentToolContext(final_k=3, request_id="request-123", langsmith_extra={"run_id": "request-123"})
    retrieved = RetrievedContext(
        docs=[
            Document(
                page_content="Refunds were allowed within 14 days in 2025.",
                metadata={"file_name": "refund_policy_2025.md", "domain": "policies", "year": "2025"},
            )
        ],
        metadata=RetrievalMetadata(
            use_hybrid=True,
            use_rerank=True,
            detected_year="2025",
            final_k=3,
            initial_k=12,
        ),
        latency_ms=12,
    )

    with patch("src.backend.app.core.agent_tools.retrieve_context", return_value=retrieved) as retrieve:
        output = search_internal_docs(context, "What was the refund window in 2025?")

    assert "refund_policy_2025.md" in output
    assert context.sources[0].file_name == "refund_policy_2025.md"
    assert context.tool_calls[0].name == "search_internal_docs"
    retrieve.assert_called_once_with(
        question="What was the refund window in 2025?",
        final_k=3,
        request_id="request-123",
        langsmith_extra={"run_id": "request-123"},
    )


def test_get_corpus_stats_returns_dashboard_metrics() -> None:
    context = AgentToolContext(final_k=5)
    snapshot = AdminDashboardSnapshot(
        retriever_backend="faiss",
        corpus=AdminCorpusStatus(
            status="healthy",
            active_documents=7,
            active_chunks=42,
            orphan_chunks=0,
            documents_without_chunks=0,
            documents_with_missing_files=0,
        ),
        metrics=[AdminMetric(label="Uploads", value="3", detail="recent uploads")],
        search_volume=[],
        latency_series=[],
        ingest_series=[],
        top_questions_week=[],
        top_questions_month=[],
        recent_jobs=[],
        recent_uploads=[],
        health_flags=[AdminHealthFlag(label="Corpus", value="healthy")],
        latest_query="refund window",
        latest_ingest_at=None,
        latest_failed_ingest_at=None,
    )

    with patch("src.backend.app.core.admin.get_admin_dashboard", return_value=snapshot):
        output = get_corpus_stats(context)

    assert '"active_documents": 7' in output
    assert '"active_chunks": 42' in output
    assert context.tool_calls[0].name == "get_corpus_stats"


def test_get_recent_ingest_jobs_filters_status() -> None:
    context = AgentToolContext(final_k=5)
    now = datetime(2026, 1, 1)
    jobs = [
        IngestJobSummary(
            id="failed-1",
            task_id="failed-1",
            source_type="upload",
            job_mode="ingest",
            status="failed",
            requested_paths=[],
            result_message=None,
            error_message="bad file",
            created_at=now,
            updated_at=now,
        ),
        IngestJobSummary(
            id="ok-1",
            task_id="ok-1",
            source_type="upload",
            job_mode="ingest",
            status="succeeded",
            requested_paths=[],
            result_message="done",
            error_message=None,
            created_at=now,
            updated_at=now,
        ),
    ]

    with patch("src.backend.app.core.ingest_jobs.list_ingest_jobs", return_value=jobs):
        output = get_recent_ingest_jobs(context, status="failed", limit=5)

    assert "failed-1" in output
    assert "ok-1" not in output
    assert context.tool_calls[0].args["status"] == "failed"


def test_tool_limits_are_clamped_for_database_reads() -> None:
    context = AgentToolContext(final_k=5)

    with patch("src.backend.app.core.search_history.list_search_history", return_value=[]) as list_history:
        get_recent_searches(context, limit=1000)

    list_history.assert_called_once()
    assert list_history.call_args.kwargs["limit"] == 100
    assert context.tool_calls[0].args["limit"] == 100

    with patch("src.backend.app.core.ingest_jobs.list_ingest_jobs", return_value=[]) as list_jobs:
        get_recent_ingest_jobs(context, status="failed", limit=0)

    list_jobs.assert_called_once()
    assert list_jobs.call_args.kwargs["limit"] == 4
    assert context.tool_calls[1].args["limit"] == 1

    with patch("src.backend.app.core.search_history.list_search_history", return_value=[]) as list_history:
        get_recent_searches(context, limit="50")

    list_history.assert_called_once()
    assert list_history.call_args.kwargs["limit"] == 50
    assert context.tool_calls[2].args["limit"] == 50
