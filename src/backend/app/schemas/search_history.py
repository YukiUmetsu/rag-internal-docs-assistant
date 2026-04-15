from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.backend.app.schemas.retrieval import Source


class SearchHistorySummary(BaseModel):
    id: str
    request_kind: str
    question: str
    requested_mode: str
    mode_used: str
    final_k: int
    initial_k: int
    detected_year: str | None
    answer_preview: str | None = None
    latency_ms: int
    source_count: int
    unique_source_count: int
    warning: str | None = None
    created_at: datetime


class SearchHistoryDetail(SearchHistorySummary):
    answer: str | None = None
    sources: list[Source]
