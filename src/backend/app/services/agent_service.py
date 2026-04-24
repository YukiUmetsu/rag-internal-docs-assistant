from __future__ import annotations

from typing import Any

from src.backend.app.core.agent_tools import (
    AgentToolContext,
    build_langchain_tools,
    get_corpus_stats,
    get_recent_ingest_jobs,
    get_recent_searches,
    search_internal_docs,
)
from src.backend.app.core.settings import get_settings
from src.backend.app.schemas.agent import AgentChatRequest, AgentChatResponse


AGENT_SYSTEM_PROMPT = """You are a controlled internal knowledge assistant.

You have access to read-only tools:
- search_internal_docs: for internal policy, HR, support, engineering, incident, refund, PTO, payment, and runbook questions.
- get_corpus_stats: for corpus/admin metrics such as document counts, chunk counts, upload counts, job counts, and corpus health.
- get_recent_ingest_jobs: for questions about ingestion jobs and failures.
- get_recent_searches: for recent search/query history.

Rules:
- Use tools for internal company facts or system metrics.
- Do not invent internal facts.
- If tool results are insufficient, say what is missing.
- Prefer at most 2 tool calls unless comparison requires more.
- Keep answers concise and cite source filenames when tool output includes them.
- Do not perform write actions."""


def agent_chat(
    request: AgentChatRequest,
    *,
    request_id: str | None = None,
    langsmith_extra: dict[str, Any] | None = None,
) -> AgentChatResponse:
    context = AgentToolContext(
        final_k=request.final_k,
        max_tool_calls=3,
        request_id=request_id,
        langsmith_extra=langsmith_extra,
    )
    normalized_mode = request.mode.strip().lower()

    if normalized_mode == "live":
        response = _try_live_agent(request, context, request_id=request_id, langsmith_extra=langsmith_extra)
        if response is not None:
            return _with_debug_preference(response, request.include_debug)
        context.warnings.append("Live agent is unavailable; used deterministic mock routing.")

    response = _mock_agent_chat(
        request,
        context,
        mode="mock" if normalized_mode != "live" else "mock_fallback",
        request_id=request_id,
    )
    return _with_debug_preference(response, request.include_debug)


def _try_live_agent(
    request: AgentChatRequest,
    context: AgentToolContext,
    *,
    request_id: str | None,
    langsmith_extra: dict[str, Any] | None,
) -> AgentChatResponse | None:
    settings = get_settings()
    if not settings.groq_model_name or not settings.groq_api_key_present:
        context.warnings.append("Live LLM is not configured; set GROQ_MODEL_NAME and GROQ_API_KEY to enable live agent mode.")
        return None

    try:
        from langchain.agents import create_agent
        from src.rag.llm import get_llm

        agent = create_agent(
            model=get_llm(),
            tools=build_langchain_tools(context),
            system_prompt=AGENT_SYSTEM_PROMPT,
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": request.question}]},
            config={
                "recursion_limit": 6,
                "run_name": "agent_chat",
                "tags": ["agent", "tool_routing"],
                "metadata": {
                    **(langsmith_extra or {}),
                    "request_id": request_id,
                    "mode": request.mode,
                    "final_k": request.final_k,
                },
            },
        )
    except Exception as exc:
        context.warnings.append(f"Live agent failed: {type(exc).__name__}: {exc}")
        return None

    answer = _extract_agent_answer(result)
    last_tool = context.tool_calls[-1].name if context.tool_calls else None
    if context.sources and _insufficient_internal_answer(answer):
        context.warnings.append("The agent did not provide enough grounded detail from retrieved internal documents.")
    return AgentChatResponse(
        request_id=request_id,
        answer=answer,
        route=_choose_route(request.question),
        last_tool=last_tool,
        tool_calls=context.tool_calls,
        warnings=context.warnings,
        sources=context.sources,
        mode="live",
    )


def _mock_agent_chat(
    request: AgentChatRequest,
    context: AgentToolContext,
    *,
    mode: str,
    request_id: str | None,
) -> AgentChatResponse:
    question = request.question
    route = _choose_route(question)

    if route == "corpus_stats":
        output = get_corpus_stats(context)
        answer = _answer_from_tool_output("Corpus stats", output)
    elif route == "ingest_jobs":
        output = get_recent_ingest_jobs(context, status=_status_filter(question), limit=5)
        answer = _answer_from_tool_output("Recent ingest jobs", output)
    elif route == "recent_searches":
        output = get_recent_searches(context, limit=5)
        answer = _answer_from_tool_output("Recent searches", output)
    elif route == "internal_docs":
        output = search_internal_docs(context, question)
        answer = _answer_from_internal_search(output, context)
    else:
        answer = _answer_general_question(question)

    return AgentChatResponse(
        request_id=request_id,
        answer=answer,
        route=route,
        last_tool=context.tool_calls[-1].name if context.tool_calls else None,
        tool_calls=context.tool_calls,
        warnings=context.warnings,
        sources=context.sources,
        mode=mode,
    )


def _choose_route(question: str) -> str:
    text = question.lower()
    if any(term in text for term in ("ingest", "job", "failed job", "running job", "queued job", "succeeded job")):
        return "ingest_jobs"
    if any(term in text for term in ("recent search", "search history", "recent quer", "user queries")):
        return "recent_searches"
    if any(term in text for term in ("corpus", "indexed", "active document", "chunk", "upload", "dashboard", "health")):
        return "corpus_stats"
    if any(
        term in text
        for term in (
            "policy",
            "hr",
            "support",
            "engineering",
            "incident",
            "refund",
            "pto",
            "payment",
            "runbook",
            "company",
            "internal",
        )
    ):
        return "internal_docs"
    return "direct"


def _status_filter(question: str) -> str | None:
    text = question.lower()
    for status in ("failed", "running", "succeeded", "queued"):
        if status in text:
            return status
    return None


def _answer_from_internal_search(output: str, context: AgentToolContext) -> str:
    if output.startswith("search_internal_docs failed:"):
        return "I could not search internal documents right now. Please try again after the retrieval service is healthy."
    if not context.sources:
        return "I could not find enough internal document evidence to answer that."

    source_names = ", ".join(dict.fromkeys(source.file_name for source in context.sources[:3]))
    return (
        "I found relevant internal context, but mock mode does not synthesize policy facts. "
        f"Review the cited sources: {source_names}."
    )


def _answer_from_tool_output(label: str, output: str) -> str:
    if " failed:" in output:
        return f"{label} are unavailable right now. The tool error is included in the trace."
    return f"{label} retrieved. See the tool trace for the bounded read-only result."


def _answer_general_question(question: str) -> str:
    text = question.lower()
    if "rag" in text:
        return "RAG, or retrieval-augmented generation, answers by retrieving relevant source context before generating a response."
    if "vector search" in text:
        return "Vector search represents text as embeddings and finds nearby items by semantic similarity."
    if "agent" in text:
        return "An agent is an LLM-driven workflow that can choose tools, inspect results, and then produce a final answer within limits."
    return "I can answer general concepts directly, but internal company facts require a read-only tool lookup."


def _extract_agent_answer(result: Any) -> str:
    if isinstance(result, dict):
        messages = result.get("messages")
        if messages:
            last = messages[-1]
            content = getattr(last, "content", None)
            if content:
                return str(content)
            if isinstance(last, dict) and last.get("content"):
                return str(last["content"])
        if result.get("output"):
            return str(result["output"])
    content = getattr(result, "content", None)
    if content:
        return str(content)
    return str(result)


def _insufficient_internal_answer(answer: str) -> bool:
    lowered = answer.lower()
    return "insufficient" in lowered or "not enough" in lowered or "could not find" in lowered


def _with_debug_preference(response: AgentChatResponse, include_debug: bool) -> AgentChatResponse:
    if include_debug:
        return response
    return response.model_copy(update={"tool_calls": []})
