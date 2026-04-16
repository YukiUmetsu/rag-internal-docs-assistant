from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

def get_vectorstore_path() -> str:
    value = os.getenv("VECTORSTORE_PATH", "artifacts/faiss_index")
    if not value:
        raise ValueError("VECTORSTORE_PATH is required")
    return value


def get_embedding_model_name() -> str:
    value = os.getenv("EMBEDDING_MODEL_NAME")
    if not value:
        raise ValueError("EMBEDDING_MODEL_NAME is required")
    return value


def get_embedding_dimension() -> int:
    value = os.getenv("EMBEDDING_DIMENSION", "384").strip()
    if not value:
        raise ValueError("EMBEDDING_DIMENSION is required")
    dimension = int(value)
    if dimension <= 0:
        raise ValueError("EMBEDDING_DIMENSION must be positive")
    return dimension


def get_rerank_model_name() -> str:
    return os.getenv(
        "RERANK_MODEL_NAME",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )


def get_chunks_path() -> str:
    return os.getenv("CHUNKS_PATH", "artifacts/chunks.jsonl")


def validate_embedding_configuration() -> None:
    model_name = get_embedding_model_name()
    expected_dimension = _known_embedding_dimension(model_name)
    configured_dimension = get_embedding_dimension()
    if expected_dimension is None:
        from sentence_transformers import SentenceTransformer

        expected_dimension = SentenceTransformer(model_name).get_sentence_embedding_dimension()
    if configured_dimension != expected_dimension:
        raise ValueError(
            "EMBEDDING_DIMENSION does not match the selected embedding model "
            f"({model_name} -> {expected_dimension}, got {configured_dimension})"
        )


def _known_embedding_dimension(model_name: str) -> int | None:
    return {
        "sentence-transformers/all-MiniLM-L6-v2": 384,
    }.get(model_name)
