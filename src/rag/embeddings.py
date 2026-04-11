from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings

from src.rag.config import get_embedding_model_name


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=get_embedding_model_name())