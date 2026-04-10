from __future__ import annotations

import argparse
from collections import defaultdict
from typing import DefaultDict, List
from langchain_core.documents import Document

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
    k: int = 8,
    max_chunks_per_source: int = 2,
) -> List[Document]:
    vectorstore = load_vectorstore()

    docs = vectorstore.similarity_search(query, k=k)

    return pick_top_chunks_per_source(
        docs,
        max_chunks_per_source=max_chunks_per_source,
    )


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