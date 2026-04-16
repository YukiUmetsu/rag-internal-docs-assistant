from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from pgvector.sqlalchemy import Vector


revision = "0006_source_documents"
down_revision = "0005_uploads"
branch_labels = None
depends_on = None


# sentence-transformers/all-MiniLM-L6-v2 produces 384-dimensional vectors.
EMBEDDING_DIMENSION = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "source_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "uploaded_file_id",
            sa.String(length=36),
            sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "ingest_job_id",
            sa.String(length=36),
            sa.ForeignKey("ingest_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "((uploaded_file_id IS NOT NULL AND source_path IS NULL) OR "
            "(uploaded_file_id IS NULL AND source_path IS NOT NULL))",
            name="ck_source_documents_one_source",
        ),
    )

    op.create_index("ix_source_documents_checksum", "source_documents", ["checksum"])
    op.create_index("ix_source_documents_is_active", "source_documents", ["is_active"])
    op.create_index("ix_source_documents_domain", "source_documents", ["domain"])
    op.create_index("ix_source_documents_topic", "source_documents", ["topic"])
    op.create_index("ix_source_documents_year", "source_documents", ["year"])
    op.create_index("ix_source_documents_ingest_job_id", "source_documents", ["ingest_job_id"])
    op.create_index(
        "uq_source_documents_uploaded_file_id",
        "source_documents",
        ["uploaded_file_id"],
        unique=True,
        postgresql_where=sa.text("uploaded_file_id IS NOT NULL AND is_active = true"),
    )
    op.create_index(
        "uq_source_documents_source_path",
        "source_documents",
        ["source_path"],
        unique=True,
        postgresql_where=sa.text("source_path IS NOT NULL AND is_active = true"),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_document_id",
            sa.String(length=36),
            sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column(
            "chunk_metadata",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("chunk_checksum", sa.String(length=128), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column(
            "search_vector",
            TSVECTOR(),
            nullable=False,
            server_default=sa.text("to_tsvector('english', '')"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index_nonnegative"),
        sa.UniqueConstraint("source_document_id", "chunk_index", name="uq_document_chunks_source_index"),
    )

    op.create_index("ix_document_chunks_source_document_id", "document_chunks", ["source_document_id"])
    op.create_index("ix_document_chunks_chunk_index", "document_chunks", ["chunk_index"])
    op.create_index(
        "ix_document_chunks_embedding",
        "document_chunks",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"lists": "100"},
    )
    op.create_index(
        "ix_document_chunks_search_vector",
        "document_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_search_vector", table_name="document_chunks")
    op.drop_index("ix_document_chunks_embedding", table_name="document_chunks")
    op.drop_index("ix_document_chunks_chunk_index", table_name="document_chunks")
    op.drop_index("ix_document_chunks_source_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("uq_source_documents_source_path", table_name="source_documents")
    op.drop_index("uq_source_documents_uploaded_file_id", table_name="source_documents")
    op.drop_index("ix_source_documents_ingest_job_id", table_name="source_documents")
    op.drop_index("ix_source_documents_year", table_name="source_documents")
    op.drop_index("ix_source_documents_topic", table_name="source_documents")
    op.drop_index("ix_source_documents_domain", table_name="source_documents")
    op.drop_index("ix_source_documents_is_active", table_name="source_documents")
    op.drop_index("ix_source_documents_checksum", table_name="source_documents")
    op.drop_table("source_documents")
