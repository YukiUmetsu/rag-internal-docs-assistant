from __future__ import annotations

import argparse
from collections import defaultdict
from typing import DefaultDict, List
from langchain_core.documents import Document

from src.rag.config import get_chunks_path
from src.rag.hybrid_retrieve import keyword_retrieve, merge_retrieval_results
from src.rag.rerank import rerank_candidates
from src.rag.vectorstore import load_vectorstore

def get_source_doc_id(doc: Document) -> str:
    return str(doc.metadata.get("source_doc_id", "unknown"))


def pick_top_chunks_per_source(
    docs: List[Document],
    max_chunks_per_source: int = 2,
) -> List[Document]:
    grouped_counts: DefaultDict[str, int] = defaultdict(int)
    selected: List[Document] = []

    for doc in docs:
        source_doc_id = get_source_doc_id(doc)

        if grouped_counts[source_doc_id] >= max_chunks_per_source:
            continue

        selected.append(doc)
        grouped_counts[source_doc_id] += 1

    return selected


def retrieve(
    query: str,
    final_k: int = 4,
    initial_k: int = 12,
    max_chunks_per_source: int = 2,
    vectorstore_path: str | None = None,
    chunks_path: str | None = None,
    use_hybrid: bool = False,
    use_rerank: bool = True,
) -> List[Document]:
    """
    Retrieve relevant documents using a two-stage retrieval pipeline.

    Pipeline:
        1. Dense retrieval (FAISS) → initial_k candidates
        2. Optional keyword retrieval (BM25) → initial_k candidates
        3. Merge candidates (deduplicate)
        4. Optional reranking (cross-encoder + freshness boost)
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

    # --- Load vectorstore ---
    vectorstore = load_vectorstore(vectorstore_path=vectorstore_path)

    # --- Stage 1: Dense retrieval ---
    dense_docs = vectorstore.similarity_search(query, k=initial_k)
    candidates: List[Document] = list(dense_docs)

    # --- Stage 2: Hybrid retrieval (optional) ---
    if use_hybrid:
        keyword_docs = keyword_retrieve(
            query=query,
            chunks_path=chunks_path or get_chunks_path(),
            k=initial_k,
        )
        candidates = merge_retrieval_results(
            dense_docs=dense_docs,
            keyword_docs=keyword_docs,
        )

    # --- Stage 3: Reranking (optional) ---
    if use_rerank:
        candidates = rerank_candidates(
            query=query,
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
    docs = retrieve(args.query, k=args.k)

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