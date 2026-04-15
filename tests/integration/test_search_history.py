from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from src.backend.app.main import app
from src.backend.app.services import rag_service


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def ensure_history_schema() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for search history integration tests")

    alembic_ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(alembic_ini_path))
    command.upgrade(config, "head")


def make_doc(file_name: str = "refund_policy_2025.md") -> Document:
    return Document(
        page_content="Refunds were allowed within 14 days in 2025.",
        metadata={
            "file_name": file_name,
            "domain": "policies",
            "topic": "refund_policy",
            "year": "2025",
            "page": 7,
        },
    )


def test_retrieve_persists_search_history() -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(rag_service, "retrieve", lambda **_: [make_doc()])
        response = client.post(
            "/api/retrieve",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "retrieve_only",
                "final_k": 4,
            },
        )

    assert response.status_code == 200

    history_response = client.get("/api/search-history", params={"limit": 10})
    assert history_response.status_code == 200
    history_items = history_response.json()
    assert history_items

    matching_item = next(
        item for item in history_items if item["question"] == "What was the refund window in 2025?"
    )
    assert matching_item["request_kind"] == "retrieve"
    assert matching_item["mode_used"] == "retrieve_only"
    assert matching_item["answer_preview"] is None
    assert matching_item["source_count"] == 1
    assert matching_item["unique_source_count"] == 1

    detail_response = client.get(f"/api/search-history/{matching_item['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["answer"] is None
    assert detail["sources"][0]["file_name"] == "refund_policy_2025.md"
    assert detail["sources"][0]["page"] == 7


def test_chat_persists_search_history() -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(rag_service, "retrieve", lambda **_: [make_doc("refund_policy_2026.md")])
        response = client.post(
            "/api/chat",
            json={
                "question": "What was the refund window in 2025?",
                "mode": "mock",
                "final_k": 4,
            },
        )

    assert response.status_code == 200

    history_response = client.get("/api/search-history", params={"limit": 10})
    assert history_response.status_code == 200
    history_items = history_response.json()
    matching_item = next(
        item
        for item in history_items
        if item["question"] == "What was the refund window in 2025?" and item["request_kind"] == "chat"
    )
    assert matching_item["mode_used"] == "mock"
    assert matching_item["answer_preview"]
    assert matching_item["answer_preview"].startswith("Mock answer based on retrieved context")

    detail_response = client.get(f"/api/search-history/{matching_item['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["answer"].startswith("Mock answer based on retrieved context")
    assert detail["sources"][0]["file_name"] == "refund_policy_2026.md"
