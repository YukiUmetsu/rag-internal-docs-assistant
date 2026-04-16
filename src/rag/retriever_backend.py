from __future__ import annotations

from enum import Enum


class RetrieverBackend(str, Enum):
    FAISS = "faiss"
    POSTGRES = "postgres"


def resolve_retriever_backend(value: str | None) -> RetrieverBackend:
    raw_value = (value or RetrieverBackend.FAISS.value).strip().lower()
    try:
        return RetrieverBackend(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive validation
        allowed = ", ".join(backend.value for backend in RetrieverBackend)
        raise ValueError(f"RETRIEVER_BACKEND must be one of: {allowed}") from exc
