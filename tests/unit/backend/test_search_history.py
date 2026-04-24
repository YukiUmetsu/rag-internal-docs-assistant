from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.core import search_history
from src.backend.app.core.search_history import (
    _FALLBACK_SEARCH_HISTORY_BY_ID,
    _FALLBACK_SEARCH_HISTORY_MAX_ENTRIES,
    _store_fallback_search_history,
    list_search_history,
    persist_search_history,
)
from src.backend.app.core.search_history import SearchHistoryDetail
from src.backend.app.schemas.retrieval import RetrievalMetadata, Source


def test_persist_search_history_logs_context_on_failure(caplog) -> None:
    retrieval = RetrievalMetadata(
        use_hybrid=True,
        use_rerank=True,
        detected_year="2026",
        final_k=4,
        initial_k=12,
    )
    sources = [
        Source(
            rank=1,
            file_name="refund_policy_2026.md",
            domain="policies",
            topic="refund_policy",
            year="2026",
            page=1,
            preview="Duplicate refunds reuse the original result.",
        )
    ]

    caplog.set_level(logging.WARNING)

    with patch("src.backend.app.core.search_history.create_engine", side_effect=SQLAlchemyError("boom")):
        result = persist_search_history(
            "postgresql://example",
            history_id="request-123",
            request_kind="chat",
            question="How do duplicate refunds work?",
            requested_mode="live",
            mode_used="live",
            retrieval=retrieval,
            sources=sources,
            latency_ms=12,
            answer="Duplicate refunds reuse the original result.",
        )

    assert result is None
    message = "\n".join(record.getMessage() for record in caplog.records)
    assert "Failed to persist search history" in message
    assert "history_id=request-123" in message
    assert "request_kind=chat" in message
    assert "question='How do duplicate refunds work?'" in message


def test_persist_search_history_uses_in_memory_fallback_when_psycopg_is_missing() -> None:
    search_history._FALLBACK_SEARCH_HISTORY_BY_ID.clear()
    retrieval = RetrievalMetadata(
        use_hybrid=True,
        use_rerank=False,
        detected_year="2026",
        final_k=4,
        initial_k=12,
    )
    sources = [
        Source(
            rank=1,
            file_name="search_history.md",
            domain="docs",
            topic="search_history",
            year="2026",
            page=1,
            preview="Recent searches are stored for review.",
        )
    ]

    with patch("src.backend.app.core.search_history.create_engine", side_effect=ModuleNotFoundError("No module named 'psycopg'")):
        history_id = persist_search_history(
            "postgresql://example",
            history_id="request-123",
            request_kind="agent",
            question="Can you show me recent searches?",
            requested_mode="mock",
            mode_used="mock",
            retrieval=retrieval,
            sources=sources,
            latency_ms=7,
            answer="Recent searches are available in memory.",
        )

    assert history_id == "request-123"
    summaries = list_search_history("postgresql://example", limit=5)
    assert summaries
    assert summaries[0].question == "Can you show me recent searches?"
    assert summaries[0].request_kind == "agent"


def test_list_search_history_logs_when_database_fallback_is_used(caplog) -> None:
    caplog.set_level(logging.ERROR)
    _FALLBACK_SEARCH_HISTORY_BY_ID.clear()

    with patch(
        "src.backend.app.core.search_history.create_engine",
        side_effect=ModuleNotFoundError("No module named 'psycopg'"),
    ):
        result = list_search_history("postgresql://user:secret@db.example:5432/app", limit=5)

    assert result == []
    message = "\n".join(record.getMessage() for record in caplog.records)
    assert "search history read fell back to in-memory store" in message
    assert "database_url=postgresql://user:***@***:5432/app" in message


def test_fallback_search_history_is_capped() -> None:
    _FALLBACK_SEARCH_HISTORY_BY_ID.clear()

    for index in range(_FALLBACK_SEARCH_HISTORY_MAX_ENTRIES + 1):
        _store_fallback_search_history(
            SearchHistoryDetail(
                id=f"request-{index:04d}",
                request_kind="agent",
                question=f"Question {index}",
                requested_mode="mock",
                mode_used="mock",
                final_k=5,
                initial_k=12,
                detected_year=None,
                answer_preview=None,
                latency_ms=1,
                source_count=0,
                unique_source_count=0,
                warning=None,
                created_at=datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc),
                answer=None,
                sources=[],
            )
        )

    assert len(_FALLBACK_SEARCH_HISTORY_BY_ID) == _FALLBACK_SEARCH_HISTORY_MAX_ENTRIES
    assert "request-0000" not in _FALLBACK_SEARCH_HISTORY_BY_ID
    assert f"request-{_FALLBACK_SEARCH_HISTORY_MAX_ENTRIES:04d}" in _FALLBACK_SEARCH_HISTORY_BY_ID
