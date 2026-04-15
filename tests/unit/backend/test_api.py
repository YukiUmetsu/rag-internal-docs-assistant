from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from src.backend.app.main import app
from src.backend.app.schemas.chat import ChatResponse
from src.backend.app.schemas.retrieval import RetrievalMetadata
from src.backend.app.services import rag_service


client = TestClient(app)


def make_doc(file_name: str = "refund_policy_2025.md") -> Document:
    return Document(
        page_content="Refunds were allowed within 14 days in 2025.",
        metadata={
            "file_name": file_name,
            "domain": "policies",
            "topic": "refund_policy",
            "year": "2025",
        },
    )


def test_health_endpoint_returns_status() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "vectorstore_available" in body
    assert "chunks_available" in body
    assert "live_llm_configured" in body


def test_retrieve_endpoint_serializes_sources() -> None:
    with patch.object(rag_service, "retrieve", return_value=[make_doc()]):
        response = client.post(
            "/api/retrieve",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "retrieve_only",
                "final_k": 4,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode_used"] == "retrieve_only"
    assert body["sources"][0]["file_name"] == "refund_policy_2025.md"
    assert body["retrieval"]["detected_year"] == "2025"


def test_retrieve_endpoint_still_succeeds_when_history_persistence_fails() -> None:
    with (
        patch.object(rag_service, "retrieve", return_value=[make_doc()]),
        patch.object(rag_service, "persist_search_history", side_effect=RuntimeError("db down")),
    ):
        response = client.post(
            "/api/retrieve",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "retrieve_only",
                "final_k": 4,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["sources"][0]["file_name"] == "refund_policy_2025.md"


def test_chat_endpoint_supports_mock_mode() -> None:
    with patch.object(rag_service, "retrieve", return_value=[make_doc()]):
        response = client.post(
            "/api/chat",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "mock",
                "final_k": 4,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode_used"] == "mock"
    assert "Mock answer" in body["answer"]
    assert body["sources"][0]["year"] == "2025"


def test_chat_endpoint_falls_back_when_live_generation_fails() -> None:
    with (
        patch.object(rag_service, "retrieve", return_value=[make_doc()]),
        patch.object(rag_service, "generate_answer_from_docs", side_effect=RuntimeError("quota")),
    ):
        response = client.post(
            "/api/chat",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "live",
                "final_k": 4,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode_used"] == "mock_fallback"
    assert "Live answer generation failed" in body["warning"]
    assert "Mock answer" in body["answer"]


def test_chat_response_schema_allows_retrieve_only_mode() -> None:
    response = ChatResponse(
        answer="Retrieved sources are ready.",
        sources=[],
        retrieval=RetrievalMetadata(
            use_hybrid=True,
            use_rerank=True,
            detected_year=None,
            final_k=4,
            initial_k=12,
        ),
        mode_used="retrieve_only",
        latency_ms=1,
    )

    assert response.mode_used == "retrieve_only"
