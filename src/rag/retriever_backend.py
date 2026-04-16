from __future__ import annotations

from enum import Enum

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


class RetrieverBackend(str, Enum):
    FAISS = "faiss"
    POSTGRES = "postgres"


RETRIEVER_BACKEND_OVERRIDE_KEY = "retriever_backend_override"


def resolve_retriever_backend(value: str | None) -> RetrieverBackend:
    raw_value = (value or RetrieverBackend.FAISS.value).strip().lower()
    try:
        return RetrieverBackend(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive validation
        allowed = ", ".join(backend.value for backend in RetrieverBackend)
        raise ValueError(f"RETRIEVER_BACKEND must be one of: {allowed}") from exc


def get_effective_retriever_backend(
    database_url: str | None,
    default_backend: str | None,
) -> RetrieverBackend:
    try:
        override = get_retriever_backend_override(database_url)
    except RuntimeError:
        return resolve_retriever_backend(default_backend)
    if override is not None:
        return override
    return resolve_retriever_backend(default_backend)


def get_retriever_backend_override(database_url: str | None) -> RetrieverBackend | None:
    if not database_url:
        return None

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT value
                    FROM app_metadata
                    WHERE key = :key
                    """
                ),
                {"key": RETRIEVER_BACKEND_OVERRIDE_KEY},
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    if row is None:
        return None
    return resolve_retriever_backend(str(row["value"]))


def set_retriever_backend_override(database_url: str | None, backend: str) -> RetrieverBackend:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    resolved = resolve_retriever_backend(backend)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO app_metadata (key, value, updated_at)
                    VALUES (:key, :value, now())
                    ON CONFLICT (key)
                    DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                    """
                ),
                {
                    "key": RETRIEVER_BACKEND_OVERRIDE_KEY,
                    "value": resolved.value,
                },
            )
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return resolved
