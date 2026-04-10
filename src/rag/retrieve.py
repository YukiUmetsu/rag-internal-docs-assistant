from __future__ import annotations

import argparse

from langchain_core.documents import Document

from src.rag.vectorstore import load_vectorstore

def retrieve(query: str, k: int = 4) -> list[Document]:
    vectorstore = load_vectorstore()
    return vectorstore.similarity_search(query, k=k)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve chunks from FAISS.")

    parser.add_argument("--query", required=True, help="Query string to search for.")
    parser.add_argument("--k", type=int, default=4, help="Number of results to return.")

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