from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from pgvector.sqlalchemy import Vector
from sqlalchemy import MetaData, Table, Column, String, Text, SmallInteger, Boolean, Integer, DateTime, BigInteger, create_engine, text, bindparam
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.exc import SQLAlchemyError

from src.rag.config import get_embedding_dimension
from src.rag.embeddings import get_embeddings


EMBEDDING_DIMENSION = get_embedding_dimension()

metadata = MetaData()

source_documents_table = Table(
    "source_documents",
    metadata,
    Column("id", String(length=36)),
    Column("source_path", Text()),
    Column("display_name", Text()),
    Column("checksum", String(length=128)),
    Column("content_type", Text()),
    Column("file_size_bytes", BigInteger()),
    Column("domain", Text()),
    Column("topic", Text()),
    Column("year", SmallInteger()),
    Column("is_active", Boolean()),
    Column("uploaded_file_id", String(length=36)),
    Column("ingest_job_id", String(length=36)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
    Column("ingested_at", DateTime(timezone=True)),
)

document_chunks_table = Table(
    "document_chunks",
    metadata,
    Column("id", String(length=36)),
    Column("source_document_id", String(length=36)),
    Column("chunk_index", Integer()),
    Column("chunk_text", Text()),
    Column("chunk_metadata", JSONB(astext_type=Text())),
    Column("chunk_checksum", String(length=128)),
    Column("embedding", Vector(EMBEDDING_DIMENSION)),
    Column("search_vector", TSVECTOR()),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)


def retrieve_dense_candidates(
    database_url: str,
    query: str,
    *,
    initial_k: int,
    query_year: str | None,
) -> list[Document]:
    query_embedding = get_embeddings().embed_query(query)
    engine = create_engine(database_url, pool_pre_ping=True)
    year_value = int(query_year) if query_year is not None else None
    if year_value is None:
        stmt = (
            text(
                """
                SELECT
                    document_chunks.id AS chunk_id,
                    document_chunks.chunk_text,
                    document_chunks.chunk_metadata,
                    source_documents.display_name,
                    source_documents.source_path,
                    source_documents.uploaded_file_id,
                    source_documents.id AS source_document_id,
                    source_documents.domain,
                    source_documents.topic,
                    source_documents.year,
                    document_chunks.chunk_index
                FROM document_chunks
                JOIN source_documents
                    ON source_documents.id = document_chunks.source_document_id
                WHERE source_documents.is_active = true
                ORDER BY document_chunks.embedding <=> :query_embedding
                LIMIT :limit
                """
            ).bindparams(bindparam("query_embedding", type_=Vector(EMBEDDING_DIMENSION)))
        )
        params = {
            "query_embedding": query_embedding,
            "limit": initial_k,
        }
    else:
        stmt = (
            text(
                """
                SELECT
                    document_chunks.id AS chunk_id,
                    document_chunks.chunk_text,
                    document_chunks.chunk_metadata,
                    source_documents.display_name,
                    source_documents.source_path,
                    source_documents.uploaded_file_id,
                    source_documents.id AS source_document_id,
                    source_documents.domain,
                    source_documents.topic,
                    source_documents.year,
                    document_chunks.chunk_index
                FROM document_chunks
                JOIN source_documents
                    ON source_documents.id = document_chunks.source_document_id
                WHERE source_documents.is_active = true
                  AND source_documents.year = :query_year
                ORDER BY document_chunks.embedding <=> :query_embedding
                LIMIT :limit
                """
            ).bindparams(bindparam("query_embedding", type_=Vector(EMBEDDING_DIMENSION)))
        )
        params = {
            "query_year": year_value,
            "query_embedding": query_embedding,
            "limit": initial_k,
        }

    return _load_documents(engine, stmt, params)


def retrieve_keyword_candidates(
    database_url: str,
    query: str,
    *,
    initial_k: int,
    query_year: str | None,
) -> list[Document]:
    engine = create_engine(database_url, pool_pre_ping=True)
    year_value = int(query_year) if query_year is not None else None
    if year_value is None:
        stmt = text(
            """
            WITH query_tsquery AS (
                SELECT websearch_to_tsquery('english', :query) AS tsquery
            )
            SELECT
                document_chunks.id AS chunk_id,
                document_chunks.chunk_text,
                document_chunks.chunk_metadata,
                source_documents.display_name,
                source_documents.source_path,
                source_documents.uploaded_file_id,
                source_documents.id AS source_document_id,
                source_documents.domain,
                source_documents.topic,
                source_documents.year,
                document_chunks.chunk_index
            FROM document_chunks
            JOIN source_documents
                ON source_documents.id = document_chunks.source_document_id
            CROSS JOIN query_tsquery
            WHERE source_documents.is_active = true
              AND document_chunks.search_vector @@ query_tsquery.tsquery
            ORDER BY ts_rank_cd(document_chunks.search_vector, query_tsquery.tsquery) DESC,
                     document_chunks.chunk_index ASC
            LIMIT :limit
            """
        )
        params = {
            "query": query,
            "limit": initial_k,
        }
    else:
        stmt = text(
            """
            WITH query_tsquery AS (
                SELECT websearch_to_tsquery('english', :query) AS tsquery
            )
            SELECT
                document_chunks.id AS chunk_id,
                document_chunks.chunk_text,
                document_chunks.chunk_metadata,
                source_documents.display_name,
                source_documents.source_path,
                source_documents.uploaded_file_id,
                source_documents.id AS source_document_id,
                source_documents.domain,
                source_documents.topic,
                source_documents.year,
                document_chunks.chunk_index
            FROM document_chunks
            JOIN source_documents
                ON source_documents.id = document_chunks.source_document_id
            CROSS JOIN query_tsquery
            WHERE source_documents.is_active = true
              AND source_documents.year = :query_year
              AND document_chunks.search_vector @@ query_tsquery.tsquery
            ORDER BY ts_rank_cd(document_chunks.search_vector, query_tsquery.tsquery) DESC,
                     document_chunks.chunk_index ASC
            LIMIT :limit
            """
        )
        params = {
            "query": query,
            "query_year": year_value,
            "limit": initial_k,
        }

    return _load_documents(engine, stmt, params)


def _load_documents(
    engine,
    stmt,
    params: dict[str, Any],
) -> list[Document]:
    try:
        with engine.connect() as connection:
            rows = connection.execute(stmt, params).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    documents: list[Document] = []
    for row in rows:
        metadata = dict(row["chunk_metadata"] or {})
        metadata["source_doc_id"] = str(row["source_document_id"])
        metadata["chunk_id"] = str(row["chunk_id"])
        metadata["file_name"] = str(row["display_name"])
        metadata["source"] = str(row["source_path"] or row["display_name"])
        metadata["domain"] = row["domain"]
        metadata["topic"] = row["topic"]
        metadata["year"] = row["year"]
        metadata["uploaded_file_id"] = row["uploaded_file_id"]
        metadata["chunk_index"] = row["chunk_index"]
        documents.append(
            Document(
                page_content=str(row["chunk_text"]),
                metadata=metadata,
            )
        )

    return documents
