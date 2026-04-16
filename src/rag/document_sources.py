from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document

from src.rag.loader import infer_metadata, load_markdown, load_pdf


SUPPORTED_SUFFIXES = {".md", ".pdf"}


def make_source_doc_id_from_value(value: str) -> str:
    normalized = value.strip().lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def checksum_for_path(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            checksum.update(chunk)
    return checksum.hexdigest()


def iter_supported_document_paths(paths: Iterable[str]) -> list[Path]:
    resolved_paths: list[Path] = []
    seen_paths: set[str] = set()

    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        candidate_paths = [path]
        if path.is_dir():
            candidate_paths = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())

        for candidate in candidate_paths:
            if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
                print(f"Skipping unsupported file type: {candidate}")
                continue

            resolved = str(candidate.resolve())
            if resolved in seen_paths:
                continue

            seen_paths.add(resolved)
            resolved_paths.append(candidate.resolve())

    return resolved_paths


def load_documents_from_paths(paths: Iterable[str]) -> list[Document]:
    documents: list[Document] = []

    for path in iter_supported_document_paths(paths):
        if path.suffix.lower() == ".md":
            documents.extend(load_markdown(path))
        elif path.suffix.lower() == ".pdf":
            documents.extend(load_pdf(path))

    return documents


def build_upload_metadata(
    *,
    original_filename: str,
    uploaded_file_id: str,
    stored_path: str,
) -> dict[str, object]:
    metadata = infer_metadata(Path(original_filename))
    metadata["source"] = stored_path
    metadata["file_name"] = original_filename
    metadata["source_doc_id"] = make_source_doc_id_from_value(f"upload:{uploaded_file_id}")
    metadata["canonical_doc_id"] = Path(original_filename).stem
    metadata["domain"] = None
    metadata["uploaded_file_id"] = uploaded_file_id
    return metadata


def apply_metadata_to_documents(
    documents: Iterable[Document],
    metadata: dict[str, object],
    *,
    preserve_keys: Iterable[str] = ("page",),
) -> list[Document]:
    """Overwrite document metadata while preserving selected keys.

    This is useful when a loader inferred metadata from a temporary or stored
    filename, but we want the final chunk metadata to reflect the original
    user-facing upload metadata instead.
    """
    preserved = tuple(preserve_keys)
    updated_documents: list[Document] = []

    for document in documents:
        retained_metadata = {
            key: document.metadata[key]
            for key in preserved
            if key in document.metadata
        }
        document.metadata.clear()
        document.metadata.update(metadata)
        document.metadata.update(retained_metadata)
        updated_documents.append(document)

    return updated_documents
