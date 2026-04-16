from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from src.backend.app.core.database import check_database_health
from src.rag.config import get_embedding_dimension, validate_embedding_configuration


def test_pgvector_migration_applies_and_extension_exists() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise AssertionError("DATABASE_URL must be configured for the integration test")

    alembic_ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(alembic_ini_path))
    command.upgrade(config, "head")

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        extension_name = connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()
        schema_stage = connection.execute(
            text("SELECT value FROM app_metadata WHERE key = 'schema_stage'")
        ).scalar_one()
        uploaded_files_table = connection.execute(
            text("SELECT to_regclass('public.uploaded_files')")
        ).scalar_one()
        ingest_job_uploads_table = connection.execute(
            text("SELECT to_regclass('public.ingest_job_uploads')")
        ).scalar_one()
        source_documents_table = connection.execute(
            text("SELECT to_regclass('public.source_documents')")
        ).scalar_one()
        document_chunks_table = connection.execute(
            text("SELECT to_regclass('public.document_chunks')")
        ).scalar_one()
        uploaded_filename_index = connection.execute(
            text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'uploaded_files'
                  AND indexname = 'ix_uploaded_files_original_filename'
                """
            )
        ).scalar_one()
        source_document_embedding_type = connection.execute(
            text(
                """
                SELECT format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'document_chunks'
                  AND a.attname = 'embedding'
                  AND a.attnum > 0
                """
            )
        ).scalar_one()

    health = check_database_health(database_url)

    assert extension_name == "vector"
    assert schema_stage == "stage_2_postgres_pgvector"
    assert uploaded_files_table == "uploaded_files"
    assert ingest_job_uploads_table == "ingest_job_uploads"
    assert source_documents_table == "source_documents"
    assert document_chunks_table == "document_chunks"
    assert uploaded_filename_index == 1
    assert source_document_embedding_type == "vector(384)"
    assert get_embedding_dimension() == 384
    validate_embedding_configuration()
    assert health.database_available is True
    assert health.pgvector_available is True
