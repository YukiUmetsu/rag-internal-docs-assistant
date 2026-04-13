from __future__ import annotations

import time
from dataclasses import dataclass

from langchain_core.documents import Document

from src.backend.app.schemas.chat import ChatRequest, ChatResponse
from src.backend.app.schemas.retrieval import RetrievalMetadata, RetrieveRequest, RetrieveResponse
from src.backend.app.utils.documents import serialize_documents
from src.rag.answer import generate_answer_from_docs
from src.rag.retrieve import get_single_query_year, retrieve


DEFAULT_INITIAL_K = 12
DEFAULT_MAX_CHUNKS_PER_SOURCE = 2
USE_HYBRID = True
USE_RERANK = True


@dataclass(frozen=True)
class RetrievedContext:
    docs: list[Document]
    metadata: RetrievalMetadata
    latency_ms: int


def retrieve_context(question: str, final_k: int) -> RetrievedContext:
    start = time.perf_counter()
    docs = retrieve(
        query=question,
        final_k=final_k,
        initial_k=DEFAULT_INITIAL_K,
        max_chunks_per_source=DEFAULT_MAX_CHUNKS_PER_SOURCE,
        use_hybrid=USE_HYBRID,
        use_rerank=USE_RERANK,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    return RetrievedContext(
        docs=docs,
        metadata=RetrievalMetadata(
            use_hybrid=USE_HYBRID,
            use_rerank=USE_RERANK,
            detected_year=get_single_query_year(question),
            final_k=final_k,
            initial_k=DEFAULT_INITIAL_K,
        ),
        latency_ms=latency_ms,
    )


def retrieve_only(request: RetrieveRequest) -> RetrieveResponse:
    context = retrieve_context(question=request.question, final_k=request.final_k)
    return RetrieveResponse(
        sources=serialize_documents(context.docs),
        retrieval=context.metadata,
        mode_used="retrieve_only",
        latency_ms=context.latency_ms,
    )


def chat(request: ChatRequest) -> ChatResponse:
    start = time.perf_counter()
    context = retrieve_context(question=request.question, final_k=request.final_k)
    warning = None

    if request.mode == "retrieve_only":
        answer = build_retrieval_only_answer(context.docs)
        mode_used = "retrieve_only"
    elif request.mode == "mock":
        answer = build_mock_answer(context.docs)
        mode_used = "mock"
    else:
        try:
            answer = generate_answer_from_docs(question=request.question, docs=context.docs)
            mode_used = "live"
        except Exception as exc:
            answer = build_mock_answer(context.docs)
            mode_used = "mock_fallback"
            warning = f"Live answer generation failed; showing mock fallback. {type(exc).__name__}: {exc}"

    latency_ms = int((time.perf_counter() - start) * 1000)
    return ChatResponse(
        answer=answer,
        sources=serialize_documents(context.docs),
        retrieval=context.metadata,
        mode_used=mode_used,
        latency_ms=latency_ms,
        warning=warning,
    )


def build_retrieval_only_answer(docs: list[Document]) -> str:
    if not docs:
        return "No matching sources were retrieved."
    return "Retrieved sources are ready for inspection. Switch to live or mock mode to generate an answer."


def build_mock_answer(docs: list[Document]) -> str:
    if not docs:
        return "I could not find enough retrieved context to answer this question."

    source_names = [
        str(doc.metadata.get("file_name", "unknown"))
        for doc in docs[:2]
    ]
    citations = ", ".join(f"Document {index}" for index in range(1, min(len(docs), 2) + 1))
    return (
        "Mock answer based on retrieved context: the most relevant sources are "
        f"{', '.join(source_names)}. Review {citations} for the grounded details. "
        "Live generation is available when Groq credentials and quota are ready."
    )
