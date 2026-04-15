from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


@dataclass(frozen=True)
class DatabaseHealth:
    database_available: bool
    pgvector_available: bool
    error: str | None = None


def check_database_health(database_url: str | None) -> DatabaseHealth:
    if not database_url:
        return DatabaseHealth(
            database_available=False,
            pgvector_available=False,
            error="DATABASE_URL is not configured",
        )

    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            pgvector_available = bool(
                connection.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                ).scalar_one()
            )
    except SQLAlchemyError as exc:
        return DatabaseHealth(
            database_available=False,
            pgvector_available=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    return DatabaseHealth(
        database_available=True,
        pgvector_available=pgvector_available,
    )
