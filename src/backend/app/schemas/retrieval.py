from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    rank: int
    file_name: str
    domain: str | None = None
    topic: str | None = None
    year: str | None = None
    page: int | str | None = None
    preview: str


class RetrievalMetadata(BaseModel):
    use_hybrid: bool
    use_rerank: bool
    detected_year: str | None
    final_k: int
    initial_k: int


class RetrieveRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    mode: Literal["live", "mock", "retrieve_only"] = "retrieve_only"
    final_k: int = Field(default=4, ge=1, le=10)


class RetrieveResponse(BaseModel):
    sources: list[Source]
    retrieval: RetrievalMetadata
    mode_used: Literal["retrieve_only"]
    latency_ms: int
    warning: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_name: str
    vectorstore_available: bool
    chunks_available: bool
    live_llm_configured: bool
    groq_model_name: str | None
    langsmith_tracing_enabled: bool
    langsmith_project: str | None
