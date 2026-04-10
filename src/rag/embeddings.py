from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings

from src.rag.config import EMBEDDING_MODEL_NAME


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)