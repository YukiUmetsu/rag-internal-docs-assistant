from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.backend.app.schemas.retrieval import RetrievalMetadata, Source


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    mode: Literal["live", "mock", "retrieve_only"] = "live"
    final_k: int = Field(default=4, ge=1, le=10)


class ChatResponse(BaseModel):
    request_id: str | None = None
    answer: str
    sources: list[Source]
    retrieval: RetrievalMetadata
    mode_used: Literal["live", "mock", "mock_fallback", "retrieve_only"]
    latency_ms: int
    warning: str | None = None
