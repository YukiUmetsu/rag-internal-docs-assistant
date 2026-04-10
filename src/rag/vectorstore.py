from __future__ import annotations

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from src.rag.config import VECTORSTORE_PATH
from src.rag.embeddings import get_embeddings


def build_vectorstore(documents: list[Document]) -> FAISS:
    embeddings = get_embeddings()
    return FAISS.from_documents(documents, embeddings)


def load_vectorstore() -> FAISS:
    embeddings = get_embeddings()
    return FAISS.load_local(
        VECTORSTORE_PATH,
        embeddings,
        allow_dangerous_deserialization=True,
    )


def save_vectorstore(vectorstore: FAISS) -> None:
    vectorstore.save_local(VECTORSTORE_PATH)