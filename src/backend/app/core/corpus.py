from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from langchain_core.documents import Document
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
    create_engine,
    func,
    insert,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.core.uploads import get_uploaded_file
from src.rag.chunking import split_documents
from src.rag.config import get_embedding_dimension
from src.rag.document_sources import (
    apply_metadata_to_documents,
    build_upload_metadata,
    checksum_for_path,
    iter_supported_document_paths,
)
from src.rag.embeddings import get_embeddings
from src.rag.loader import infer_metadata, load_markdown, load_pdf


EMBEDDING_DIMENSION = get_embedding_dimension()

metadata = MetaData()

source_documents_table = Table(
    "source_documents",
    metadata,
    Column("id", String(length=36), primary_key=True),
    Column("uploaded_file_id", String(length=36), ForeignKey("uploaded_files.id", ondelete="RESTRICT")),
    Column("source_path", Text()),
    Column("display_name", Text(), nullable=False),
    Column("checksum", String(length=128), nullable=False),
    Column("content_type", Text()),
    Column("file_size_bytes", BigInteger()),
    Column("domain", Text()),
    Column("topic", Text()),
    Column("year", SmallInteger()),
    Column("is_active", Boolean(), nullable=False),
    Column("ingest_job_id", String(length=36), ForeignKey("ingest_jobs.id", ondelete="SET NULL")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True)),
)

document_chunks_table = Table(
    "document_chunks",
    metadata,
    Column("id", String(length=36), primary_key=True),
    Column("source_document_id", String(length=36), ForeignKey("source_documents.id", ondelete="CASCADE")),
    Column("chunk_index", Integer(), nullable=False),
    Column("chunk_text", Text(), nullable=False),
    Column("chunk_metadata", JSONB(astext_type=Text()), nullable=False),
    Column("chunk_checksum", String(length=128), nullable=False),
    Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
    Column("search_vector", TSVECTOR(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True)
class PreparedCorpusSource:
    source_lookup_column: str
    source_lookup_value: str
    source_document_row: dict[str, Any]
    chunk_rows: list[dict[str, Any]]
    chunk_ids: list[str]


@dataclass(frozen=True)
class CorpusIngestResult:
    source_documents_inserted: int
    source_documents_replaced: int
    source_documents_skipped: int
    chunks_inserted: int


@dataclass(frozen=True)
class CorpusIntegrityIssue:
    code: str
    message: str


@dataclass(frozen=True)
class CorpusIntegrityReport:
    active_source_documents: int
    active_document_chunks: int
    orphan_chunk_count: int
    source_documents_without_chunks: int
    documents_with_missing_files: int
    issues: list[CorpusIntegrityIssue]

    @property
    def is_healthy(self) -> bool:
        return not self.issues


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


def persist_prepared_sources(
    database_url: str | None,
    *,
    ingest_job_id: str,
    prepared_sources: list[PreparedCorpusSource],
    full_refresh: bool,
) -> CorpusIngestResult:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    now = datetime.now(timezone.utc)
    source_documents_inserted = 0
    source_documents_replaced = 0
    source_documents_skipped = 0
    chunks_inserted = 0

    try:
        with engine.begin() as connection:
            if full_refresh:
                connection.execute(
                    text(
                        """
                        UPDATE source_documents
                        SET is_active = false,
                            updated_at = :now
                        WHERE is_active = true
                        """
                    ),
                    {"now": now},
                )

            for prepared in prepared_sources:
                existing = _get_active_source_document(
                    connection,
                    prepared.source_lookup_column,
                    prepared.source_lookup_value,
                )

                if not full_refresh and existing is not None:
                    if str(existing["checksum"]) == str(prepared.source_document_row["checksum"]):
                        source_documents_skipped += 1
                        continue

                    connection.execute(
                        update(source_documents_table)
                        .where(source_documents_table.c.id == existing["id"])
                        .values(
                            is_active=False,
                            updated_at=now,
                        )
                    )
                    source_documents_replaced += 1

                connection.execute(insert(source_documents_table), [prepared.source_document_row])
                if prepared.chunk_rows:
                    connection.execute(insert(document_chunks_table), prepared.chunk_rows)
                    connection.execute(
                        update(document_chunks_table)
                        .where(document_chunks_table.c.id.in_(prepared.chunk_ids))
                        .values(
                            search_vector=func.to_tsvector("english", document_chunks_table.c.chunk_text),
                            updated_at=now,
                        )
                    )
                source_documents_inserted += 1
                chunks_inserted += len(prepared.chunk_rows)
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return CorpusIngestResult(
        source_documents_inserted=source_documents_inserted,
        source_documents_replaced=source_documents_replaced,
        source_documents_skipped=source_documents_skipped,
        chunks_inserted=chunks_inserted,
    )


def count_active_corpus_rows(database_url: str | None) -> dict[str, int]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            source_documents = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM source_documents
                        WHERE is_active = true
                        """
                    )
                ).scalar_one()
            )
            chunks = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM document_chunks
                        JOIN source_documents
                            ON source_documents.id = document_chunks.source_document_id
                        WHERE source_documents.is_active = true
                        """
                    )
                ).scalar_one()
            )
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return {
        "source_documents": source_documents,
        "document_chunks": chunks,
    }


def count_source_document_versions(database_url: str | None, *, source_path: str) -> dict[str, int]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS total_count,
                        COUNT(*) FILTER (WHERE is_active = true) AS active_count
                    FROM source_documents
                    WHERE source_path = :source_path
                    """
                ),
                {"source_path": source_path},
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    if row is None:
        return {"total_count": 0, "active_count": 0}

    return {
        "total_count": int(row["total_count"]),
        "active_count": int(row["active_count"]),
    }


def count_corpus_rows_for_job(database_url: str | None, *, ingest_job_id: str) -> dict[str, int]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        COUNT(DISTINCT source_documents.id) AS source_documents_count,
                        COUNT(document_chunks.id) AS document_chunks_count
                    FROM source_documents
                    LEFT JOIN document_chunks
                        ON document_chunks.source_document_id = source_documents.id
                    WHERE source_documents.ingest_job_id = :ingest_job_id
                    """
                ),
                {"ingest_job_id": ingest_job_id},
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    if row is None:
        return {"source_documents_count": 0, "document_chunks_count": 0}

    return {
        "source_documents_count": int(row["source_documents_count"]),
        "document_chunks_count": int(row["document_chunks_count"]),
    }


def verify_corpus_integrity(database_url: str | None) -> CorpusIntegrityReport:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    issues: list[CorpusIntegrityIssue] = []

    try:
        with engine.connect() as connection:
            active_source_documents = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM source_documents
                        WHERE is_active = true
                        """
                    )
                ).scalar_one()
            )
            active_document_chunks = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM document_chunks
                        JOIN source_documents
                            ON source_documents.id = document_chunks.source_document_id
                        WHERE source_documents.is_active = true
                        """
                    )
                ).scalar_one()
            )
            orphan_chunk_count = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM document_chunks
                        LEFT JOIN source_documents
                            ON source_documents.id = document_chunks.source_document_id
                        WHERE source_documents.id IS NULL
                        """
                    )
                ).scalar_one()
            )
            source_documents_without_chunks = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM (
                            SELECT source_documents.id
                            FROM source_documents
                            LEFT JOIN document_chunks
                                ON document_chunks.source_document_id = source_documents.id
                            WHERE source_documents.is_active = true
                            GROUP BY source_documents.id
                            HAVING COUNT(document_chunks.id) = 0
                        ) AS missing_chunks
                        """
                    )
                ).scalar_one()
            )
            missing_file_rows = connection.execute(
                text(
                    """
                    SELECT
                        source_documents.id,
                        source_documents.display_name,
                        source_documents.uploaded_file_id,
                        source_documents.source_path
                    FROM source_documents
                    WHERE source_documents.is_active = true
                    """
                )
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    for row in missing_file_rows:
        uploaded_file_id = row["uploaded_file_id"]
        source_path = row["source_path"]
        if uploaded_file_id is not None:
            try:
                get_uploaded_file(database_url, str(uploaded_file_id))
            except KeyError:
                issues.append(
                    CorpusIntegrityIssue(
                        code="missing_uploaded_file",
                        message=f"Active document {row['display_name']} references missing upload {uploaded_file_id}",
                    )
                )
        if source_path is not None and not Path(str(source_path)).exists():
            issues.append(
                CorpusIntegrityIssue(
                    code="missing_source_path",
                    message=f"Active document {row['display_name']} points to missing file {source_path}",
                )
            )

    if active_source_documents == 0:
        issues.append(
            CorpusIntegrityIssue(
                code="no_active_source_documents",
                message="No active source documents are available",
            )
        )
    if active_document_chunks == 0:
        issues.append(
            CorpusIntegrityIssue(
                code="no_active_document_chunks",
                message="No active document chunks are available",
            )
        )
    if orphan_chunk_count > 0:
        issues.append(
            CorpusIntegrityIssue(
                code="orphan_chunks",
                message=f"Found {orphan_chunk_count} chunk(s) without a source document",
            )
        )
    if source_documents_without_chunks > 0:
        issues.append(
            CorpusIntegrityIssue(
                code="source_documents_without_chunks",
                message=f"Found {source_documents_without_chunks} active source document(s) without chunks",
            )
        )

    return CorpusIntegrityReport(
        active_source_documents=active_source_documents,
        active_document_chunks=active_document_chunks,
        orphan_chunk_count=orphan_chunk_count,
        source_documents_without_chunks=source_documents_without_chunks,
        documents_with_missing_files=len(
            [
                issue
                for issue in issues
                if issue.code in {"missing_uploaded_file", "missing_source_path"}
            ]
        ),
        issues=issues,
    )


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
        source_path=source_path,
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
            "content_type": content_type or _guess_content_type(original_filename),
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
        content_type=content_type or _guess_content_type(original_filename),
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
    source_document_row: dict[str, Any],
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

    chunk_rows: list[dict[str, Any]] = []
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


def _get_active_source_document(
    connection: Any,
    lookup_column: str,
    lookup_value: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        text(
            f"""
            SELECT id, checksum, is_active
            FROM source_documents
            WHERE {lookup_column} = :lookup_value
              AND is_active = true
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ),
        {"lookup_value": lookup_value},
    ).mappings().first()
    return dict(row) if row is not None else None


def _chunk_checksum(source_document_id: str, chunk_index: int, chunk_text: str) -> str:
    checksum = hashlib.sha256()
    checksum.update(source_document_id.encode("utf-8"))
    checksum.update(b":")
    checksum.update(str(chunk_index).encode("utf-8"))
    checksum.update(b":")
    checksum.update(chunk_text.encode("utf-8"))
    return checksum.hexdigest()


def _coerce_year(value: Any) -> int | None:
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
