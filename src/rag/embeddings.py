from __future__ import annotations

import warnings

from langchain_huggingface import HuggingFaceEmbeddings

from src.rag.config import get_embedding_model_name


def get_embeddings() -> HuggingFaceEmbeddings:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=FutureWarning,
            message=".*resume_download.*",
        )
        return HuggingFaceEmbeddings(model_name=get_embedding_model_name())
