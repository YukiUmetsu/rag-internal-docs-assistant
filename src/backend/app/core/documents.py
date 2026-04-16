from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


@dataclass(frozen=True)
class SourceDocumentSummary:
    id: str
    source_kind: str
    display_name: str
    source_path: str | None
    uploaded_file_id: str | None
    ingest_job_id: str | None
    domain: str | None
    topic: str | None
    year: int | None
    content_type: str | None
    file_size_bytes: int | None
    checksum: str
    is_active: bool
    chunk_count: int
    created_at: Any
    updated_at: Any
    ingested_at: Any


@dataclass(frozen=True)
class SourceDocumentDetail(SourceDocumentSummary):
    total_chunk_count: int


def count_source_documents(database_url: str | None, *, active_only: bool = False) -> int:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM source_documents
                    WHERE (:active_only = false OR is_active = true)
                    """
                ),
                {"active_only": active_only},
            ).scalar_one()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return int(row)


def list_source_documents(
    database_url: str | None,
    *,
    limit: int = 20,
    offset: int = 0,
    active_only: bool = False,
) -> list[SourceDocumentSummary]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        source_documents.id,
                        CASE
                            WHEN source_documents.uploaded_file_id IS NULL THEN 'mounted_data'
                            ELSE 'uploaded_files'
                        END AS source_kind,
                        source_documents.display_name,
                        source_documents.source_path,
                        source_documents.uploaded_file_id,
                        source_documents.ingest_job_id,
                        source_documents.domain,
                        source_documents.topic,
                        source_documents.year,
                        source_documents.content_type,
                        source_documents.file_size_bytes,
                        source_documents.checksum,
                        source_documents.is_active,
                        COALESCE(chunk_counts.chunk_count, 0) AS chunk_count,
                        source_documents.created_at,
                        source_documents.updated_at,
                        source_documents.ingested_at
                    FROM source_documents
                    LEFT JOIN (
                        SELECT
                            source_document_id,
                            COUNT(*) AS chunk_count
                        FROM document_chunks
                        GROUP BY source_document_id
                    ) AS chunk_counts
                        ON chunk_counts.source_document_id = source_documents.id
                    WHERE (:active_only = false OR source_documents.is_active = true)
                    ORDER BY source_documents.created_at DESC, source_documents.id DESC
                    LIMIT :limit
                    OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset, "active_only": active_only},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [_summary_from_row(row) for row in rows]


def get_source_document(database_url: str | None, document_id: str) -> SourceDocumentDetail:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        source_documents.id,
                        CASE
                            WHEN source_documents.uploaded_file_id IS NULL THEN 'mounted_data'
                            ELSE 'uploaded_files'
                        END AS source_kind,
                        source_documents.display_name,
                        source_documents.source_path,
                        source_documents.uploaded_file_id,
                        source_documents.ingest_job_id,
                        source_documents.domain,
                        source_documents.topic,
                        source_documents.year,
                        source_documents.content_type,
                        source_documents.file_size_bytes,
                        source_documents.checksum,
                        source_documents.is_active,
                        COALESCE(chunk_counts.chunk_count, 0) AS chunk_count,
                        COALESCE(chunk_counts.chunk_count, 0) AS total_chunk_count,
                        source_documents.created_at,
                        source_documents.updated_at,
                        source_documents.ingested_at
                    FROM source_documents
                    LEFT JOIN (
                        SELECT
                            source_document_id,
                            COUNT(*) AS chunk_count
                        FROM document_chunks
                        GROUP BY source_document_id
                    ) AS chunk_counts
                        ON chunk_counts.source_document_id = source_documents.id
                    WHERE source_documents.id = :document_id
                    """
                ),
                {"document_id": document_id},
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    if row is None:
        raise KeyError(document_id)

    return _detail_from_row(row)


def _summary_from_row(row: dict[str, Any]) -> SourceDocumentSummary:
    return SourceDocumentSummary(
        id=str(row["id"]),
        source_kind=str(row["source_kind"]),
        display_name=str(row["display_name"]),
        source_path=row["source_path"],
        uploaded_file_id=row["uploaded_file_id"],
        ingest_job_id=row["ingest_job_id"],
        domain=row["domain"],
        topic=row["topic"],
        year=row["year"],
        content_type=row["content_type"],
        file_size_bytes=row["file_size_bytes"],
        checksum=str(row["checksum"]),
        is_active=bool(row["is_active"]),
        chunk_count=int(row["chunk_count"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        ingested_at=row["ingested_at"],
    )


def _detail_from_row(row: dict[str, Any]) -> SourceDocumentDetail:
    return SourceDocumentDetail(
        **_summary_from_row(row).model_dump(),
        total_chunk_count=int(row["total_chunk_count"]),
    )

