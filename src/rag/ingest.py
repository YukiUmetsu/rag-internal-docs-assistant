from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from langchain_core.documents import Document

from src.rag.chunking import split_documents
from src.rag.loader import load_all_documents, load_markdown, load_pdf
from src.rag.vectorstore import build_vectorstore, load_vectorstore, save_vectorstore


def load_documents_from_paths(paths: List[str]) -> List[Document]:
    docs: List[Document] = []

    for raw_path in paths:
        path = Path(raw_path)

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Path does not exist or is not a file: {path}")

        if path.suffix == ".md":
            docs.extend(load_markdown(path))
        elif path.suffix == ".pdf":
            docs.extend(load_pdf(path))
        else:
            print(f"Skipping unsupported file type: {path}")

    return docs


def run_full_update() -> None:
    print("Running full update...")

    documents = load_all_documents()
    print(f"Loaded {len(documents)} documents/pages")

    chunks = split_documents(documents)
    print(f"Created {len(chunks)} chunks")

    print("Building FAISS index from scratch...")
    vectorstore = build_vectorstore(chunks)

    print("Saving index...")
    save_vectorstore(vectorstore)

    print("Full update complete.")


def run_partial_update(paths: List[str]) -> None:
    if not paths:
        raise ValueError("Partial update requires at least one file path via --paths")

    print("Running partial update...")
    print("Warning: partial update appends documents and does not remove old chunks.")

    documents = load_documents_from_paths(paths)
    print(f"Loaded {len(documents)} documents/pages from selected files")

    chunks = split_documents(documents)
    print(f"Created {len(chunks)} chunks")

    print("Loading existing FAISS index...")
    vectorstore = load_vectorstore()

    print("Adding new chunks to existing index...")
    vectorstore.add_documents(chunks)

    print("Saving updated index...")
    save_vectorstore(vectorstore)

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