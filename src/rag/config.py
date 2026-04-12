from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

def get_vectorstore_path() -> str:
    value = os.getenv("VECTORSTORE_PATH")
    if not value:
        raise ValueError("VECTORSTORE_PATH is required")
    return value


def get_embedding_model_name() -> str:
    value = os.getenv("EMBEDDING_MODEL_NAME")
    if not value:
        raise ValueError("EMBEDDING_MODEL_NAME is required")
    return value


def get_rerank_model_name() -> str:
    return os.getenv(
        "RERANK_MODEL_NAME",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )

def get_chunks_path() -> str:
    return os.getenv("CHUNKS_PATH", "artifacts/chunks.jsonl")