from __future__ import annotations

import argparse
import re
from collections import defaultdict
from typing import DefaultDict, List
from langchain_core.documents import Document

from src.rag.config import get_chunks_path
from src.rag.debug_log import append_rerank_debug_log
from src.rag.hybrid_retrieve import keyword_retrieve, merge_retrieval_results
from src.rag.postgres_retrieve import retrieve_dense_candidates, retrieve_keyword_candidates
from src.rag.rerank import rerank_candidates
from src.rag.retriever_backend import (
    RetrieverBackend,
    get_effective_retriever_backend,
    resolve_retriever_backend,
)
from src.rag.vectorstore import load_vectorstore
from src.backend.app.core.settings import get_settings


def get_single_query_year(query: str) -> str | None:
    years = set(re.findall(r"\b(20\d{2})\b", query))
    if len(years) != 1:
        return None
    return next(iter(years))


def filter_docs_by_year(docs: List[Document], year: str | None) -> List[Document]:
    if year is None:
        return docs
    return [doc for doc in docs if str(doc.metadata.get("year")) == year]


def get_group_id(doc: Document) -> str:
    return (
        doc.metadata.get("canonical_doc_id")
        or doc.metadata.get("source_doc_id")
        or "unknown"
    )

def pick_top_chunks_per_source(
    docs: List[Document],
    max_chunks_per_source: int = 2,
) -> List[Document]:
    grouped_counts: DefaultDict[str, int] = defaultdict(int)
    selected: List[Document] = []

    for doc in docs:
        group_id = get_group_id(doc)

        if grouped_counts[group_id] >= max_chunks_per_source:
            continue

        selected.append(doc)
        grouped_counts[group_id] += 1

    return selected


def retrieve(
    query: str,
    final_k: int = 4,
    initial_k: int = 12,
    max_chunks_per_source: int = 2,
    vectorstore_path: str | None = None,
    chunks_path: str | None = None,
    retriever_backend: str | None = None,
    use_hybrid: bool = True,
    use_rerank: bool = True,
    debug_log_path: str | None = None,
    debug_context: dict[str, str] | None = None,
) -> List[Document]:
    """
    Retrieve relevant documents using a two-stage retrieval pipeline.

    Pipeline:
        1. Dense retrieval (FAISS) → initial_k candidates
        2. Optional keyword retrieval (BM25) → initial_k candidates
        3. Merge candidates (deduplicate)
        4. Optional reranking (cross-encoder + metadata score adjustment)
        5. Limit chunks per source
        6. Return top final_k documents

    Args:
        query: User query
        initial_k: Number of candidates retrieved before reranking (recall stage)
        final_k: Number of documents returned after all processing (precision stage)
        max_chunks_per_source: Limit chunks from the same source document
        vectorstore_path: Path to FAISS index
        chunks_path: Path to persisted chunk corpus (for BM25)
        use_hybrid: Whether to include keyword (BM25) retrieval
        use_rerank: Whether to apply cross-encoder reranking

    Returns:
        List of top-ranked documents
    """

    settings = get_settings()
    if retriever_backend is not None:
        backend = resolve_retriever_backend(retriever_backend)
    else:
        backend = get_effective_retriever_backend(settings.database_url, settings.retriever_backend)
    query_year = get_single_query_year(query)

    # --- Stage 1: Dense retrieval ---
    if backend == RetrieverBackend.FAISS:
        vectorstore = load_vectorstore(vectorstore_path=vectorstore_path)
        if query_year is None:
            dense_docs = vectorstore.similarity_search(query, k=initial_k)
        else:
            dense_docs = vectorstore.similarity_search(
                query,
                k=initial_k,
                filter={"year": query_year},
                fetch_k=max(initial_k * 5, 50),
            )
            if not dense_docs and not use_hybrid:
                dense_docs = vectorstore.similarity_search(query, k=initial_k)
    else:
        database_url = settings.database_url
        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        dense_docs = retrieve_dense_candidates(
            database_url,
            query,
            initial_k=initial_k,
            query_year=query_year,
        )
        if query_year is not None and not dense_docs and not use_hybrid:
            dense_docs = retrieve_dense_candidates(
                database_url,
                query,
                initial_k=initial_k,
                query_year=None,
            )

    candidates: List[Document] = list(dense_docs)

    # --- Stage 2: Hybrid retrieval (optional) ---
    if use_hybrid:
        keyword_fetch_k = initial_k * 4 if query_year is not None else initial_k
        if backend == RetrieverBackend.FAISS:
            raw_keyword_docs = keyword_retrieve(
                query=query,
                chunks_path=chunks_path or get_chunks_path(),
                k=keyword_fetch_k,
            )
            keyword_docs = filter_docs_by_year(raw_keyword_docs, query_year)
            if query_year is not None and not dense_docs and not keyword_docs:
                vectorstore = load_vectorstore(vectorstore_path=vectorstore_path)
                dense_docs = vectorstore.similarity_search(query, k=initial_k)
                keyword_docs = raw_keyword_docs
            keyword_docs = keyword_docs[:initial_k]
        else:
            database_url = settings.database_url
            if not database_url:
                raise RuntimeError("DATABASE_URL is not configured")
            raw_keyword_docs = retrieve_keyword_candidates(
                database_url,
                query,
                initial_k=keyword_fetch_k,
                query_year=query_year,
            )
            keyword_docs = raw_keyword_docs[:initial_k]
            if query_year is not None and not dense_docs and not keyword_docs:
                dense_docs = retrieve_dense_candidates(
                    database_url,
                    query,
                    initial_k=initial_k,
                    query_year=None,
                )
                keyword_docs = retrieve_keyword_candidates(
                    database_url,
                    query,
                    initial_k=initial_k,
                    query_year=None,
                )

        candidates = merge_retrieval_results(
            dense_docs=dense_docs,
            keyword_docs=keyword_docs,
        )

    # --- Stage 3: Reranking (optional) ---
    if use_rerank:
        query_id = debug_context.get("query_id") if debug_context else None
        mode_name = debug_context.get("mode_name") if debug_context else None

        if debug_log_path:
            append_rerank_debug_log(
                path=debug_log_path,
                query_id=query_id,
                query=query,
                mode_name=mode_name,
                stage="before_rerank",
                docs=candidates,
            )

        candidates = rerank_candidates(
            query=query,
            docs=candidates,
            use_metadata_score_adjustment=True,
        )

        if debug_log_path:
            append_rerank_debug_log(
                path=debug_log_path,
                query_id=query_id,
                query=query,
                mode_name=mode_name,
                stage="after_rerank",
                docs=candidates,
            )

    # --- Stage 4: Per-source filtering ---
    filtered_docs = pick_top_chunks_per_source(
        candidates,
        max_chunks_per_source=max_chunks_per_source,
    )

    # --- Stage 5: Final selection ---
    return filtered_docs[:final_k]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve chunks from FAISS.")

    parser.add_argument("--query", required=True, help="Query string to search for.")
    parser.add_argument("--k", type=int, default=8, help="Number of results to return.")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    docs = retrieve(args.query, final_k=args.k)

    print(f"Retrieved {len(docs)} documents.\n")

    for i, doc in enumerate(docs, start=1):
        print(f"Result {i}")
        print("Metadata:")
        print(doc.metadata)
        print("\nContent:")
        print(doc.page_content[:800])
        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
