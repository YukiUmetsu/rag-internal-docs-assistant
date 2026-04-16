from __future__ import annotations

import pytest

from src.rag.retriever_backend import RetrieverBackend, resolve_retriever_backend


def test_resolve_retriever_backend_defaults_to_faiss() -> None:
    assert resolve_retriever_backend(None) == RetrieverBackend.FAISS


def test_resolve_retriever_backend_parses_postgres() -> None:
    assert resolve_retriever_backend("postgres") == RetrieverBackend.POSTGRES


def test_resolve_retriever_backend_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        resolve_retriever_backend("not-a-backend")
