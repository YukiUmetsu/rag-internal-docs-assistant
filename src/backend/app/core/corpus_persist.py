from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, insert, text, update
from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.core.corpus_schema import (
    CorpusIngestResult,
    PreparedCorpusSource,
    document_chunks_table,
    source_documents_table,
)


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

    return {"source_documents": source_documents, "document_chunks": chunks}


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

    return {"total_count": int(row["total_count"]), "active_count": int(row["active_count"])}


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
