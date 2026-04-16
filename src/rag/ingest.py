from __future__ import annotations

import argparse

from langchain_core.documents import Document

from src.rag.chunk_store import save_chunks
from src.rag.config import get_chunks_path
from src.rag.chunking import split_documents
from src.rag.document_sources import load_documents_from_paths
from src.rag.loader import load_all_documents
from src.rag.vectorstore import build_vectorstore, load_vectorstore, save_vectorstore


def run_full_update_from_paths(
    paths: list[str],
    vectorstore_path: str | None = None,
    chunks_path: str | None = None,
) -> None:
    documents = load_documents_from_paths(paths)
    run_full_update_from_documents(documents, vectorstore_path=vectorstore_path, chunks_path=chunks_path)


def run_full_update_from_documents(
    documents: list[Document],
    vectorstore_path: str | None = None,
    chunks_path: str | None = None,
) -> None:
    print("Running full update...")
    print(f"Loaded {len(documents)} documents/pages")
    chunks = split_documents(documents)
    print(f"Created {len(chunks)} chunks")

    save_chunks(chunks, chunks_path or get_chunks_path())

    print("Building FAISS index from scratch...")
    vectorstore = build_vectorstore(chunks)
    print("Saving index...")
    save_vectorstore(vectorstore, vectorstore_path=vectorstore_path)
    print("Full update complete.")


def run_full_update() -> None:
    documents = load_all_documents()
    run_full_update_from_documents(documents)


def run_partial_update(
    paths: list[str],
    vectorstore_path: str | None = None,
    chunks_path: str | None = None,
) -> None:
    if not paths:
        raise ValueError("Partial update requires at least one file path via --paths")

    print("Running partial update...")
    print("Warning: partial update appends documents and does not remove old chunks.")

    documents = load_documents_from_paths(paths)
    print(f"Loaded {len(documents)} documents/pages from selected files")

    chunks = split_documents(documents)
    print(f"Created {len(chunks)} chunks")

    save_chunks(chunks, chunks_path or get_chunks_path())

    print("Loading existing FAISS index...")
    vectorstore = load_vectorstore(vectorstore_path)

    print("Adding new chunks to existing index...")
    vectorstore.add_documents(chunks)

    print("Saving updated index...")
    save_vectorstore(vectorstore, vectorstore_path)

    print("Partial update complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest documents into FAISS.")

    parser.add_argument(
        "--mode",
        choices=["full", "partial"],
        default="full",
        help="Ingestion mode. Default is full.",
    )

    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Specific file paths for partial update.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == "full":
        run_full_update()
    else:
        run_partial_update(args.paths)


if __name__ == "__main__":
    main()
