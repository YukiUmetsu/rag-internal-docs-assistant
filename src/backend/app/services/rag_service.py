from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document
from langsmith import traceable

from src.backend.app.core.tracing import get_langsmith_project
from src.backend.app.schemas.chat import ChatRequest, ChatResponse
from src.backend.app.schemas.retrieval import RetrievalMetadata, RetrieveRequest, RetrieveResponse
from src.backend.app.utils.documents import serialize_documents
from src.rag.answer import generate_answer_from_docs
from src.rag.retrieve import get_single_query_year, retrieve


DEFAULT_INITIAL_K = 12
DEFAULT_MAX_CHUNKS_PER_SOURCE = 2
USE_HYBRID = True
USE_RERANK = True
LANGSMITH_PROJECT = get_langsmith_project()


@dataclass(frozen=True)
class RetrievedContext:
    docs: list[Document]
    metadata: RetrievalMetadata
    latency_ms: int


def summarize_documents_for_trace(docs: list[Document]) -> list[dict[str, Any]]:
    return [
        {
            "rank": index,
            "file_name": doc.metadata.get("file_name"),
            "domain": doc.metadata.get("domain"),
            "topic": doc.metadata.get("topic"),
            "year": doc.metadata.get("year"),
            "page": doc.metadata.get("page"),
            "content_chars": len(doc.page_content),
        }
        for index, doc in enumerate(docs, start=1)
    ]


def summarize_retrieved_context(context: RetrievedContext) -> dict[str, Any]:
    source_files = [
        str(doc.metadata.get("file_name", "unknown"))
        for doc in context.docs
    ]
    retrieval_metadata = (
        context.metadata.model_dump()
        if hasattr(context.metadata, "model_dump")
        else context.metadata.dict()
    )
    return {
        "latency_ms": context.latency_ms,
        "source_count": len(context.docs),
        "unique_source_count": len(set(source_files)),
        "source_files": source_files,
        "sources": summarize_documents_for_trace(context.docs),
        "retrieval": retrieval_metadata,
    }


def summarize_request_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    request = inputs.get("request")
    if request is None:
        return inputs
    return {
        "question": request.question,
        "question_chars": len(request.question),
        "mode": request.mode,
        "final_k": request.final_k,
    }


def summarize_chat_response(response: ChatResponse) -> dict[str, Any]:
    source_files = [source.file_name for source in response.sources]
    return {
        "mode_used": response.mode_used,
        "latency_ms": response.latency_ms,
        "answer_chars": len(response.answer),
        "source_count": len(response.sources),
        "unique_source_count": len(set(source_files)),
        "source_files": source_files,
        "detected_year": response.retrieval.detected_year,
        "warning": bool(response.warning),
    }


def summarize_retrieve_response(response: RetrieveResponse) -> dict[str, Any]:
    source_files = [source.file_name for source in response.sources]
    return {
        "mode_used": response.mode_used,
        "latency_ms": response.latency_ms,
        "source_count": len(response.sources),
        "unique_source_count": len(set(source_files)),
        "source_files": source_files,
        "detected_year": response.retrieval.detected_year,
    }


@traceable(
    name="retrieve_context",
    run_type="retriever",
    project_name=LANGSMITH_PROJECT,
    tags=["rag", "retrieval", "hybrid", "rerank"],
    process_outputs=summarize_retrieved_context,
)
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


@traceable(
    name="retrieve_only",
    run_type="chain",
    project_name=LANGSMITH_PROJECT,
    tags=["rag", "api", "retrieve_only"],
    process_inputs=summarize_request_inputs,
    process_outputs=summarize_retrieve_response,
)
def retrieve_only(request: RetrieveRequest) -> RetrieveResponse:
    context = retrieve_context(question=request.question, final_k=request.final_k)
    return RetrieveResponse(
        sources=serialize_documents(context.docs),
        retrieval=context.metadata,
        mode_used="retrieve_only",
        latency_ms=context.latency_ms,
    )


@traceable(
    name="chat",
    run_type="chain",
    project_name=LANGSMITH_PROJECT,
    tags=["rag", "api", "chat"],
    process_inputs=summarize_request_inputs,
    process_outputs=summarize_chat_response,
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
