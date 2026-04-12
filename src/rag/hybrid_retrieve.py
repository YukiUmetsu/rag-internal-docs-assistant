from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever

from src.rag.chunk_store import load_chunks

_BM25_CACHE: dict[str, BM25Retriever] = {}


def get_bm25_retriever(
    chunks_path: str,
    k: int,
) -> BM25Retriever:
    if chunks_path not in _BM25_CACHE:
        docs = load_chunks(chunks_path)
        retriever = BM25Retriever.from_documents(docs)
        _BM25_CACHE[chunks_path] = retriever

    retriever = _BM25_CACHE[chunks_path]
    retriever.k = k
    return retriever


def keyword_retrieve(
    query: str,
    chunks_path: str,
    k: int,
) -> list[Document]:
    retriever = get_bm25_retriever(chunks_path=chunks_path, k=k)
    return list(retriever.invoke(query))


def _merge_key(doc: Document) -> tuple[str, str, int]:
    source_doc_id = str(
        doc.metadata.get("source_doc_id")
        or doc.metadata.get("source")
        or doc.metadata.get("file_name")
        or "unknown"
    )
    page = str(doc.metadata.get("page", ""))
    content_hash = hash(doc.page_content)
    return source_doc_id, page, content_hash


def merge_retrieval_results(
    dense_docs: list[Document],
    keyword_docs: list[Document],
) -> list[Document]:
    merged: dict[tuple[str, str, int], Document] = {}

    for doc in dense_docs + keyword_docs:
        key = _merge_key(doc)
        if key not in merged:
            merged[key] = doc

    return list(merged.values())
