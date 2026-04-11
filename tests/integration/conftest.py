"""Semi-integration: fast FAISS tests without downloading real embedding models."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from langchain_core.embeddings import FakeEmbeddings


@pytest.fixture(autouse=True)
def _fake_embeddings_for_integration():
    fake = FakeEmbeddings(size=64)
    with patch("src.rag.vectorstore.get_embeddings", lambda: fake):
        yield
