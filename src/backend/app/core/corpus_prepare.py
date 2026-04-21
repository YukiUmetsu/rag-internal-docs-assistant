from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from langchain_core.documents import Document

from src.backend.app.core.corpus_schema import PreparedCorpusSource
from src.backend.app.core.uploads import get_uploaded_file
from src.rag.chunking import split_documents
from src.rag.document_sources import (
    apply_metadata_to_documents,
    build_upload_metadata,
    checksum_for_path,
    iter_supported_document_paths,
)
from src.rag.embeddings import get_embeddings
from src.rag.loader import infer_metadata, load_markdown, load_pdf


def collect_prepared_sources(
    database_url: str | None,
    *,
    requested_paths: Iterable[str],
    uploaded_file_ids: Iterable[str],
    ingest_job_id: str,
) -> list[PreparedCorpusSource]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    prepared: list[PreparedCorpusSource] = []
    now = datetime.now(timezone.utc)

    for path in iter_supported_document_paths(requested_paths):
        prepared.append(_prepare_source_from_path(path, ingest_job_id=ingest_job_id, now=now))

    for upload_id in _normalize_ids(uploaded_file_ids):
        uploaded_file = get_uploaded_file(database_url, upload_id)
        uploaded_path = Path(uploaded_file.stored_path)
        if not uploaded_path.exists():
            raise FileNotFoundError(
                f"Uploaded file is missing from disk: {uploaded_file.original_filename}"
            )
        prepared.append(
            _prepare_source_from_upload(
                uploaded_file_id=uploaded_file.id,
                original_filename=uploaded_file.original_filename,
                stored_path=uploaded_file.stored_path,
                content_type=uploaded_file.content_type,
                file_size_bytes=uploaded_file.file_size_bytes,
                checksum=uploaded_file.checksum,
                ingest_job_id=ingest_job_id,
                now=now,
            )
        )

    return prepared


def _prepare_source_from_path(path: Path, *, ingest_job_id: str, now: datetime) -> PreparedCorpusSource:
    if path.suffix.lower() == ".md":
        documents = load_markdown(path)
        content_type = "text/markdown"
    elif path.suffix.lower() == ".pdf":
        documents = load_pdf(path)
        content_type = "application/pdf"
    else:  # pragma: no cover - protected by iter_supported_document_paths
        raise ValueError(f"Unsupported file type: {path}")

    metadata = infer_metadata(path)
    display_name = path.name
    checksum = checksum_for_path(path)
    source_document_id = str(uuid.uuid4())
    source_path = str(path.resolve())

    return _prepare_source_document(
        documents=documents,
        source_document_id=source_document_id,
        source_lookup_column="source_path",
        source_lookup_value=source_path,
        source_document_row={
            "id": source_document_id,
            "uploaded_file_id": None,
            "source_path": source_path,
            "display_name": display_name,
            "checksum": checksum,
            "content_type": content_type,
            "file_size_bytes": path.stat().st_size,
            "domain": metadata.get("domain") or None,
            "topic": metadata.get("topic") or None,
            "year": _coerce_year(metadata.get("year")),
            "is_active": True,
            "ingest_job_id": ingest_job_id,
            "created_at": now,
            "updated_at": now,
            "ingested_at": now,
        },
        ingest_job_id=ingest_job_id,
        display_name=display_name,
        checksum=checksum,
        content_type=content_type,
        file_size_bytes=path.stat().st_size,
        source_path=str(path.resolve()),
        uploaded_file_id=None,
        original_filename=path.name,
        now=now,
    )


def _prepare_source_from_upload(
    *,
    uploaded_file_id: str,
    original_filename: str,
    stored_path: str,
    content_type: str | None,
    file_size_bytes: int,
    checksum: str,
    ingest_job_id: str,
    now: datetime,
) -> PreparedCorpusSource:
    path = Path(stored_path)
    if path.suffix.lower() == ".md":
        documents = load_markdown(path)
    elif path.suffix.lower() == ".pdf":
        documents = load_pdf(path)
    else:
        raise ValueError(f"Unsupported uploaded file type: {original_filename}")

    metadata = build_upload_metadata(
        original_filename=original_filename,
        uploaded_file_id=uploaded_file_id,
        stored_path=stored_path,
    )
    documents = apply_metadata_to_documents(documents, metadata)
    source_document_id = str(uuid.uuid4())
    resolved_content_type = content_type or _guess_content_type(original_filename)

    return _prepare_source_document(
        documents=documents,
        source_document_id=source_document_id,
        source_lookup_column="uploaded_file_id",
        source_lookup_value=uploaded_file_id,
        source_document_row={
            "id": source_document_id,
            "uploaded_file_id": uploaded_file_id,
            "source_path": None,
            "display_name": original_filename,
            "checksum": checksum,
            "content_type": resolved_content_type,
            "file_size_bytes": file_size_bytes,
            "domain": metadata.get("domain") or None,
            "topic": metadata.get("topic") or None,
            "year": _coerce_year(metadata.get("year")),
            "is_active": True,
            "ingest_job_id": ingest_job_id,
            "created_at": now,
            "updated_at": now,
            "ingested_at": now,
        },
        ingest_job_id=ingest_job_id,
        display_name=original_filename,
        checksum=checksum,
        content_type=resolved_content_type,
        file_size_bytes=file_size_bytes,
        source_path=stored_path,
        uploaded_file_id=uploaded_file_id,
        original_filename=original_filename,
        now=now,
    )


def _prepare_source_document(
    *,
    documents: list[Document],
    source_document_id: str,
    source_lookup_column: str,
    source_lookup_value: str,
    source_document_row: dict[str, object],
    ingest_job_id: str,
    display_name: str,
    checksum: str,
    content_type: str | None,
    file_size_bytes: int,
    source_path: str,
    uploaded_file_id: str | None,
    original_filename: str,
    now: datetime,
) -> PreparedCorpusSource:
    chunks = split_documents(documents)
    if not chunks:
        raise ValueError(f"No chunks were produced for {display_name}")

    embeddings = get_embeddings().embed_documents([chunk.page_content for chunk in chunks])
    if len(embeddings) != len(chunks):
        raise RuntimeError(
            f"Expected {len(chunks)} embeddings for {display_name}, received {len(embeddings)}"
        )

    chunk_rows: list[dict[str, object]] = []
    chunk_ids: list[str] = []
    for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = str(uuid.uuid4())
        chunk_ids.append(chunk_id)
        chunk_metadata = {
            **chunk.metadata,
            "source_document_id": source_document_id,
            "ingest_job_id": ingest_job_id,
            "display_name": display_name,
            "original_filename": original_filename,
            "source_path": source_path,
            "uploaded_file_id": uploaded_file_id,
            "chunk_index": index,
            "chunk_count": len(chunks),
            "checksum": checksum,
            "content_type": content_type,
            "file_size_bytes": file_size_bytes,
        }
        chunk_rows.append(
            {
                "id": chunk_id,
                "source_document_id": source_document_id,
                "chunk_index": index,
                "chunk_text": chunk.page_content,
                "chunk_metadata": json.loads(json.dumps(chunk_metadata, default=str)),
                "chunk_checksum": _chunk_checksum(source_document_id, index, chunk.page_content),
                "embedding": embedding,
                "created_at": now,
                "updated_at": now,
            }
        )

    return PreparedCorpusSource(
        source_lookup_column=source_lookup_column,
        source_lookup_value=source_lookup_value,
        source_document_row=source_document_row,
        chunk_rows=chunk_rows,
        chunk_ids=chunk_ids,
    )


def _chunk_checksum(source_document_id: str, chunk_index: int, chunk_text: str) -> str:
    checksum = hashlib.sha256()
    checksum.update(source_document_id.encode("utf-8"))
    checksum.update(b":")
    checksum.update(str(chunk_index).encode("utf-8"))
    checksum.update(b":")
    checksum.update(chunk_text.encode("utf-8"))
    return checksum.hexdigest()


def _coerce_year(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    value_str = str(value).strip()
    if not value_str:
        return None
    try:
        return int(value_str)
    except ValueError:
        return None


def _guess_content_type(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    if suffix == ".md":
        return "text/markdown"
    if suffix == ".pdf":
        return "application/pdf"
    return None


def _normalize_ids(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        stripped = str(value).strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return normalized
