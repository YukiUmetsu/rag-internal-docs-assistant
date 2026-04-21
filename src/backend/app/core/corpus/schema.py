from __future__ import annotations

from dataclasses import dataclass

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
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from src.rag.config import get_embedding_dimension


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
    source_document_row: dict[str, object]
    chunk_rows: list[dict[str, object]]
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
