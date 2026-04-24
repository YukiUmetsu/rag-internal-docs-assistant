from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.backend.app.main import app
from src.backend.app.schemas.agent import AgentChatRequest, AgentChatResponse
from src.backend.app.services.agent_service import agent_chat


client = TestClient(app)


def test_agent_endpoint_exists_and_validates_request() -> None:
    missing_question = client.post("/api/agent/chat", json={})
    assert missing_question.status_code == 422

    response = client.post("/api/agent/chat", json={"question": "What is RAG?"})
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "direct"
    assert body["tool_calls"] == []
    assert body["request_id"] is not None


def test_agent_endpoint_threads_request_id_to_service() -> None:
    agent_response = AgentChatResponse(
        request_id="request-123",
        answer="ok",
        route="direct",
        mode="mock",
    )
    with (
        patch("src.backend.app.core.request_ids.generate_request_id", return_value="request-123"),
        patch("src.backend.app.services.agent_service.agent_chat", return_value=agent_response) as chat_service,
    ):
        response = client.post("/api/agent/chat", json={"question": "What is RAG?"})

    assert response.status_code == 200
    assert response.json()["request_id"] == "request-123"
    chat_service.assert_called_once()
    assert chat_service.call_args.kwargs["request_id"] == "request-123"
    assert chat_service.call_args.kwargs["langsmith_extra"] == {"run_id": "request-123"}


def test_agent_mock_routes_corpus_question_to_stats_tool() -> None:
    with patch("src.backend.app.core.admin.get_admin_dashboard", side_effect=RuntimeError("db down")):
        response = agent_chat(AgentChatRequest(question="How many active documents are indexed?", include_debug=True))

    assert response.route == "corpus_stats"
    assert response.last_tool == "get_corpus_stats"
    assert response.tool_calls[0].name == "get_corpus_stats"
    assert response.warnings
    assert "unavailable" in response.answer


def test_agent_mock_routes_refund_question_to_internal_search() -> None:
    with patch(
        "src.backend.app.services.agent_service.search_internal_docs",
        return_value='{"sources": [{"file_name": "refund_policy_2025.md"}]}',
    ) as search_tool:
        response = agent_chat(AgentChatRequest(question="What is the refund window in 2025?", include_debug=True))

    assert response.route == "internal_docs"
    search_tool.assert_called_once()


def test_agent_mock_routes_failed_jobs_to_ingest_tool() -> None:
    with patch(
        "src.backend.app.services.agent_service.get_recent_ingest_jobs",
        return_value='{"jobs": []}',
    ) as jobs_tool:
        response = agent_chat(AgentChatRequest(question="Show failed ingest jobs", include_debug=True))

    assert response.route == "ingest_jobs"
    jobs_tool.assert_called_once()
    assert jobs_tool.call_args.kwargs["status"] == "failed"


def test_agent_handles_tool_failure_gracefully() -> None:
    with patch("src.backend.app.core.admin.get_admin_dashboard", side_effect=RuntimeError("database unavailable")):
        response = client.post(
            "/api/agent/chat",
            json={"question": "How is corpus health?", "mode": "mock", "include_debug": True},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "corpus_stats"
    assert body["warnings"]
    assert body["tool_calls"][0]["name"] == "get_corpus_stats"


def test_agent_omits_tool_calls_when_debug_is_false() -> None:
    with patch("src.backend.app.core.admin.get_admin_dashboard", side_effect=RuntimeError("db down")):
        response = agent_chat(AgentChatRequest(question="How many active documents are indexed?", include_debug=False))

    assert response.route == "corpus_stats"
    assert response.tool_calls == []
    assert response.warnings


def test_live_llm_missing_uses_mock_fallback_without_api_key() -> None:
    missing_llm_settings = SimpleNamespace(groq_model_name=None, groq_api_key_present=False)
    with patch("src.backend.app.services.agent_service.get_settings", return_value=missing_llm_settings):
        response = client.post(
            "/api/agent/chat",
            json={"question": "What is RAG?", "mode": "live"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock_fallback"
    assert body["warnings"]
