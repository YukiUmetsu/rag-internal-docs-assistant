from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.backend.app.schemas.retrieval import Source


class AgentChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    mode: str = Field(default="mock")
    final_k: int = Field(default=5, ge=1, le=10)
    include_debug: bool = False


class AgentToolCall(BaseModel):
    name: str
    args: dict[str, Any] | str
    output_preview: str | None = None


class AgentChatResponse(BaseModel):
    request_id: str | None = None
    answer: str
    route: str | None = Field(
        default=None,
        description=(
            "Stable question category, such as internal_docs, corpus_stats, ingest_jobs, "
            "recent_searches, or direct. In live mode, use last_tool to inspect the "
            "actual tool most recently called by the LangChain agent."
        ),
    )
    last_tool: str | None = None
    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    mode: str
