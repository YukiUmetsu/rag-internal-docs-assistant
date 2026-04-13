from __future__ import annotations

import hashlib
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever

from src.rag.chunk_store import load_chunks

_BM25_CACHE: dict[str, BM25Retriever] = {}
DEFAULT_RRF_K = 60


@dataclass
class FusedResult:
    doc: Document
    score: float = 0.0
    best_rank: int = 10**9
    first_seen: int = 10**9


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


def _stable_content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _merge_key(doc: Document) -> tuple[str, str, str]:
    source_doc_id = str(
        doc.metadata.get("source_doc_id")
        or doc.metadata.get("source")
        or doc.metadata.get("file_name")
        or "unknown"
    )
    page = str(doc.metadata.get("page", ""))
    content_hash = _stable_content_hash(doc.page_content)
    return source_doc_id, page, content_hash


def merge_retrieval_results(
    dense_docs: list[Document],
    keyword_docs: list[Document],
    *,
    rrf_k: int = DEFAULT_RRF_K,
    dense_weight: float = 1.0,
    keyword_weight: float = 1.0,
) -> list[Document]:
    fused: dict[tuple[str, str, str], FusedResult] = {}
    first_seen = 0

    for docs, weight in (
        (dense_docs, dense_weight),
        (keyword_docs, keyword_weight),
    ):
        for rank, doc in enumerate(docs, start=1):
            key = _merge_key(doc)

            if key not in fused:
                fused[key] = FusedResult(doc=doc, first_seen=first_seen)
                first_seen += 1

            item = fused[key]
            item.score += weight / (rrf_k + rank)
            item.best_rank = min(item.best_rank, rank)

    ranked = sorted(
        fused.values(),
        key=lambda item: (-item.score, item.best_rank, item.first_seen),
    )

    return [item.doc for item in ranked]
