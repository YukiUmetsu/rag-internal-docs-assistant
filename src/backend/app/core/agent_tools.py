from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from src.backend.app.core.settings import get_settings
from src.backend.app.schemas.agent import AgentToolCall
from src.backend.app.schemas.retrieval import RetrievalMetadata
from src.backend.app.schemas.retrieval import Source
from src.backend.app.services.rag_service import retrieve_context
from src.backend.app.utils.datetime_display import parse_display_datetime
from src.backend.app.utils.documents import serialize_documents


@dataclass
class AgentToolContext:
    final_k: int
    max_tool_calls: int = 3
    request_id: str | None = None
    langsmith_extra: dict[str, Any] | None = None
    client_timezone: str | None = None
    retrieval_metadata: RetrievalMetadata | None = None
    tool_calls: list[AgentToolCall] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


def execute_traced_tool(
    context: AgentToolContext,
    name: str,
    args: dict[str, Any],
    operation: Callable[[], str],
) -> str:
    if len(context.tool_calls) >= context.max_tool_calls:
        output = f"{name} skipped: maximum tool call limit of {context.max_tool_calls} was reached."
        context.warnings.append(output)
        context.tool_calls.append(
            AgentToolCall(
                name=name,
                args=args,
                output_preview=_preview(output),
            )
        )
        return output

    try:
        output = operation()
    except Exception as exc:  # pragma: no cover - exercised through callers
        output = f"{name} failed: {type(exc).__name__}: {exc}"
        context.warnings.append(output)

    context.tool_calls.append(
        AgentToolCall(
            name=name,
            args=args,
            output_preview=_preview(output),
        )
    )
    return output


def search_internal_docs(context: AgentToolContext, question: str) -> str:
    """Use for internal policy, HR, support, engineering, incident, refund, PTO, payment, and runbook questions."""

    def operation() -> str:
        retrieved = retrieve_context(
            question=question,
            final_k=context.final_k,
            request_id=context.request_id,
            langsmith_extra=context.langsmith_extra,
        )
        context.retrieval_metadata = retrieved.metadata
        sources = serialize_documents(retrieved.docs)
        context.sources = sources
        if not sources:
            return "No internal document context was retrieved."

        snippets = [
            {
                "rank": source.rank,
                "file_name": source.file_name,
                "domain": source.domain,
                "topic": source.topic,
                "year": source.year,
                "page": source.page,
                "snippet": source.preview,
            }
            for source in sources
        ]
        return json.dumps({"sources": snippets}, default=str)

    return execute_traced_tool(
        context,
        "search_internal_docs",
        {"question": question},
        operation,
    )


def get_corpus_stats(context: AgentToolContext) -> str:
    """Use for corpus/admin metrics such as document counts, chunk counts, upload counts, job counts, and corpus health."""

    def operation() -> str:
        try:
            from src.backend.app.core.admin import get_admin_dashboard

            settings = get_settings()
            dashboard = get_admin_dashboard(settings.database_url, retriever_backend=settings.retriever_backend)
        except (ModuleNotFoundError, ImportError, RuntimeError) as exc:
            detail = _db_unavailable_detail(exc)
            context.warnings.append(f"Corpus stats are unavailable right now. {detail}")
            return "Corpus stats are unavailable right now."

        payload = {
            "retriever_backend": dashboard.retriever_backend,
            "corpus": asdict(dashboard.corpus),
            "metrics": [asdict(metric) for metric in dashboard.metrics],
            "recent_upload_count": len(dashboard.recent_uploads),
            "recent_job_count": len(dashboard.recent_jobs),
            "latest_query": dashboard.latest_query,
            "latest_ingest_at": dashboard.latest_ingest_at,
            "latest_failed_ingest_at": dashboard.latest_failed_ingest_at,
            "health_flags": [asdict(flag) for flag in dashboard.health_flags],
        }
        return json.dumps(payload, default=str)

    return execute_traced_tool(context, "get_corpus_stats", {}, operation)


def get_recent_ingest_jobs(
    context: AgentToolContext,
    status: str | None = None,
    limit: int = 5,
) -> str:
    """Use for recent, failed, running, queued, or succeeded ingestion jobs."""

    safe_limit = _clamp_limit(limit)

    def operation() -> str:
        try:
            from src.backend.app.core.ingest_jobs import list_ingest_jobs

            settings = get_settings()
            fetch_limit = _clamp_limit(safe_limit * 4) if status else safe_limit
            jobs = list_ingest_jobs(settings.database_url, limit=fetch_limit)
        except (ModuleNotFoundError, ImportError, RuntimeError) as exc:
            detail = _db_unavailable_detail(exc)
            context.warnings.append(f"Recent ingest jobs are unavailable right now. {detail}")
            return "Recent ingest jobs are unavailable right now."

        if status:
            normalized_status = status.strip().lower()
            jobs = [job for job in jobs if job.status.lower() == normalized_status]
        jobs = jobs[:safe_limit]
        payload = [
            {
                "id": job.id,
                "status": job.status,
                "source_type": job.source_type,
                "job_mode": job.job_mode,
                "result_message": job.result_message,
                "error_message": job.error_message,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }
            for job in jobs
        ]
        return json.dumps({"jobs": payload}, default=str)

    args: dict[str, Any] = {"limit": safe_limit}
    if status:
        args["status"] = status
    return execute_traced_tool(context, "get_recent_ingest_jobs", args, operation)


def get_recent_searches(context: AgentToolContext, limit: int = 5) -> str:
    """Use for recent search history or recent user query questions."""

    safe_limit = _clamp_limit(limit)

    def operation() -> str:
        try:
            from src.backend.app.core.search_history import list_search_history

            settings = get_settings()
            history = list_search_history(settings.database_url, limit=safe_limit)
        except (ModuleNotFoundError, ImportError, RuntimeError) as exc:
            detail = _db_unavailable_detail(exc)
            context.warnings.append(f"Recent searches are unavailable right now. {detail}")
            return "Recent searches are unavailable right now."

        if not history:
            return "No recent searches were found."

        lines = ["Recent searches"]
        for index, item in enumerate(history[:safe_limit], start=1):
            created_at = parse_display_datetime(item.created_at, context.client_timezone)
            lines.append(f"{index}. {item.question}\n   {item.request_kind} · {created_at}")
        return "\n".join(lines)

    return execute_traced_tool(context, "get_recent_searches", {"limit": safe_limit}, operation)


def build_langchain_tools(context: AgentToolContext) -> list[Any]:
    try:
        from langchain.tools import tool
    except Exception as exc:  # pragma: no cover - depends on optional runtime install
        raise RuntimeError("LangChain tools are unavailable") from exc

    @tool
    def search_internal_docs_tool(question: str) -> str:
        """Use for internal policy, HR, support, engineering, incident, refund, PTO, payment, and runbook questions."""
        return search_internal_docs(context, question)

    @tool
    def get_corpus_stats_tool() -> str:
        """Use for corpus/admin metrics such as document counts, chunk counts, uploads, job counts, and health."""
        return get_corpus_stats(context)

    @tool
    def get_recent_ingest_jobs_tool(status: str | None = None, limit: int = 5) -> str:
        """Use for recent, failed, running, queued, or succeeded ingestion jobs."""
        return get_recent_ingest_jobs(context, status=status, limit=limit)

    @tool
    def get_recent_searches_tool(limit: int = 5) -> str:
        """Use for recent search history or recent user query questions."""
        return get_recent_searches(context, limit=limit)

    search_internal_docs_tool.name = "search_internal_docs"
    get_corpus_stats_tool.name = "get_corpus_stats"
    get_recent_ingest_jobs_tool.name = "get_recent_ingest_jobs"
    get_recent_searches_tool.name = "get_recent_searches"
    return [
        search_internal_docs_tool,
        get_corpus_stats_tool,
        get_recent_ingest_jobs_tool,
        get_recent_searches_tool,
    ]


def _preview(output: str, limit: int = 500) -> str:
    compact = " ".join(output.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _clamp_limit(limit: int, *, minimum: int = 1, maximum: int = 100) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = minimum
    return max(minimum, min(value, maximum))


def _db_unavailable_detail(exc: Exception) -> str:
    if isinstance(exc, (ModuleNotFoundError, ImportError)) and "psycopg" in str(exc):
        return "The PostgreSQL driver is not installed in this runtime."
    return f"{type(exc).__name__}: {exc}"
