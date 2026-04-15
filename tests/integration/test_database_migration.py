from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from src.backend.app.core.database import check_database_health


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

    health = check_database_health(database_url)

    assert extension_name == "vector"
    assert schema_stage == "stage_2_postgres_pgvector"
    assert health.database_available is True
    assert health.pgvector_available is True
