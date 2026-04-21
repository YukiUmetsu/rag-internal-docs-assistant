from __future__ import annotations

import logging
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.core.search_history import persist_search_history
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
