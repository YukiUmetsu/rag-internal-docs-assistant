from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.core.queue.app import celery_app
from src.backend.app.core.uploads import (
    get_uploaded_file,
    _insert_ingest_job_upload_links,
)
from src.backend.app.core.settings import get_settings


@dataclass(frozen=True)
class IngestJobSummary:
    id: str
    task_id: str | None
    source_type: str
    job_mode: str
    status: str
    requested_paths: list[str]
    result_message: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    uploaded_file_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IngestJobDetail(IngestJobSummary):
    started_at: datetime | None = None
    finished_at: datetime | None = None


def create_ingest_job(
    database_url: str | None,
    *,
    source_type: str,
    job_mode: str,
    requested_paths: list[str],
    uploaded_file_ids: list[str] | None = None,
) -> IngestJobDetail:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    normalized_paths = _normalize_paths(requested_paths)
    normalized_uploaded_file_ids = _normalize_ids(uploaded_file_ids or [])
    _ensure_uploaded_files_exist(database_url, normalized_uploaded_file_ids)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            # Keep the DB job id and Celery task id aligned for now so a job
            # has one stable identifier across API, DB, and worker logs.
            # We still store both fields so we can split them later if retries
            # or replays need separate Celery task ids.
            connection.execute(
                text(
                    """
                    INSERT INTO ingest_jobs (
                        id,
                        task_id,
                        source_type,
                        job_mode,
                        status,
                        requested_paths,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :task_id,
                        :source_type,
                        :job_mode,
                        :status,
                        :requested_paths,
                        :created_at,
                        :updated_at
                    )
                    """
                ),
                {
                    "id": job_id,
                    "task_id": job_id,
                    "source_type": source_type,
                    "job_mode": job_mode,
                    "status": "queued",
                    "requested_paths": json.dumps(normalized_paths),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            _insert_ingest_job_upload_links(connection, job_id, normalized_uploaded_file_ids, now)
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return get_ingest_job(database_url, job_id)


def list_ingest_jobs(database_url: str | None, limit: int = 20) -> list[IngestJobSummary]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        ingest_jobs.id,
                        ingest_jobs.task_id,
                        ingest_jobs.source_type,
                        ingest_jobs.job_mode,
                        ingest_jobs.status,
                        ingest_jobs.requested_paths,
                        COALESCE(upload_links.uploaded_file_ids, ARRAY[]::text[]) AS uploaded_file_ids,
                        ingest_jobs.result_message,
                        ingest_jobs.error_message,
                        ingest_jobs.created_at,
                        ingest_jobs.updated_at
                    FROM ingest_jobs
                    LEFT JOIN (
                        SELECT
                            ingest_job_id,
                            array_agg(uploaded_file_id) AS uploaded_file_ids
                        FROM ingest_job_uploads
                        GROUP BY ingest_job_id
                    ) AS upload_links
                        ON upload_links.ingest_job_id = ingest_jobs.id
                    ORDER BY ingest_jobs.created_at DESC, ingest_jobs.id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [_summary_from_row(row) for row in rows]


def get_ingest_job(database_url: str | None, job_id: str) -> IngestJobDetail:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        ingest_jobs.id,
                        ingest_jobs.task_id,
                        ingest_jobs.source_type,
                        ingest_jobs.job_mode,
                        ingest_jobs.status,
                        ingest_jobs.requested_paths,
                        COALESCE(upload_links.uploaded_file_ids, ARRAY[]::text[]) AS uploaded_file_ids,
                        ingest_jobs.result_message,
                        ingest_jobs.error_message,
                        ingest_jobs.created_at,
                        ingest_jobs.updated_at,
                        ingest_jobs.started_at,
                        ingest_jobs.finished_at
                    FROM ingest_jobs
                    LEFT JOIN (
                        SELECT
                            ingest_job_id,
                            array_agg(uploaded_file_id) AS uploaded_file_ids
                        FROM ingest_job_uploads
                        GROUP BY ingest_job_id
                    ) AS upload_links
                        ON upload_links.ingest_job_id = ingest_jobs.id
                    WHERE ingest_jobs.id = :job_id
                    """
                ),
                {"job_id": job_id},
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    if row is None:
        raise KeyError(job_id)

    return _detail_from_row(row)


def enqueue_validation_ingest_job(
    database_url: str | None,
    *,
    source_type: str,
    job_mode: str,
    requested_paths: list[str],
    uploaded_file_ids: list[str] | None = None,
) -> IngestJobDetail:
    normalized_paths = _normalize_paths(requested_paths)
    normalized_uploaded_file_ids = _normalize_ids(uploaded_file_ids or [])
    _ensure_requested_inputs(normalized_paths, normalized_uploaded_file_ids)
    job = create_ingest_job(
        database_url,
        source_type=source_type,
        job_mode=job_mode,
        requested_paths=normalized_paths,
        uploaded_file_ids=normalized_uploaded_file_ids,
    )
    validation_ingest_job.apply_async(args=[job.id], task_id=job.id)
    return job


def enqueue_document_ingest_job(
    database_url: str | None,
    *,
    source_type: str,
    job_mode: str,
    requested_paths: list[str],
    uploaded_file_ids: list[str] | None = None,
) -> IngestJobDetail:
    normalized_paths = _normalize_paths(requested_paths)
    normalized_uploaded_file_ids = _normalize_ids(uploaded_file_ids or [])
    _ensure_requested_inputs(normalized_paths, normalized_uploaded_file_ids)
    job = create_ingest_job(
        database_url,
        source_type=source_type,
        job_mode=job_mode,
        requested_paths=normalized_paths,
        uploaded_file_ids=normalized_uploaded_file_ids,
    )
    document_ingest_job.apply_async(args=[job.id], task_id=job.id)
    return job


@celery_app.task(name="ingest_jobs.validation")
def validation_ingest_job(job_id: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    mark_ingest_job_started(settings.database_url, job_id)
    # Keep a brief visible running state so async job transitions are easy to
    # observe in tests and in the UI while this remains a validation-only task.
    time.sleep(1.0)

    job = get_ingest_job(settings.database_url, job_id)
    normalized_paths = job.requested_paths
    uploaded_file_ids = job.uploaded_file_ids
    missing_paths = [path for path in normalized_paths if not Path(path).exists()]
    missing_uploads: list[str] = []
    for upload_id in uploaded_file_ids:
        try:
            uploaded_file = get_uploaded_file(settings.database_url, upload_id)
        except KeyError:
            missing_uploads.append(upload_id)
            continue
        if not Path(uploaded_file.stored_path).exists():
            missing_uploads.append(f"{upload_id} ({uploaded_file.stored_path})")
    if missing_paths:
        error_message = f"Missing requested paths: {', '.join(missing_paths)}"
        mark_ingest_job_failed(settings.database_url, job_id, error_message)
        raise FileNotFoundError(error_message)
    if missing_uploads:
        error_message = f"Missing uploaded files: {', '.join(missing_uploads)}"
        mark_ingest_job_failed(settings.database_url, job_id, error_message)
        raise FileNotFoundError(error_message)

    result_message = (
        f"Validated {len(normalized_paths)} requested path(s) and "
        f"{len(uploaded_file_ids)} uploaded file(s)."
    )
    mark_ingest_job_succeeded(settings.database_url, job_id, result_message)
    return {
        "job_id": job_id,
        "status": "succeeded",
        "result_message": result_message,
        "validated_paths": normalized_paths,
        "validated_uploaded_file_ids": uploaded_file_ids,
    }


@celery_app.task(name="ingest_jobs.document_ingest")
def document_ingest_job(job_id: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    mark_ingest_job_started(settings.database_url, job_id)
    job = get_ingest_job(settings.database_url, job_id)

    try:
        from src.backend.app.core.corpus.prepare import collect_prepared_sources
        from src.backend.app.core.corpus.persist import persist_prepared_sources

        prepared_sources = collect_prepared_sources(
            settings.database_url,
            requested_paths=job.requested_paths,
            uploaded_file_ids=job.uploaded_file_ids,
            ingest_job_id=job_id,
        )
        if not prepared_sources:
            raise ValueError("No ingest sources were provided.")

        result = persist_prepared_sources(
            settings.database_url,
            ingest_job_id=job_id,
            prepared_sources=prepared_sources,
            full_refresh=job.job_mode == "full",
        )
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        mark_ingest_job_failed(settings.database_url, job_id, error_message)
        raise

    result_message = (
        "Ingested "
        f"{result.source_documents_inserted} source document(s), "
        f"{result.chunks_inserted} chunk(s), "
        f"skipped {result.source_documents_skipped} unchanged source document(s)."
    )
    if result.source_documents_replaced:
        result_message += f" Replaced {result.source_documents_replaced} stale source document(s)."

    mark_ingest_job_succeeded(settings.database_url, job_id, result_message)
    return {
        "job_id": job_id,
        "status": "succeeded",
        "result_message": result_message,
        "source_documents_inserted": result.source_documents_inserted,
        "source_documents_replaced": result.source_documents_replaced,
        "source_documents_skipped": result.source_documents_skipped,
        "chunks_inserted": result.chunks_inserted,
    }


def mark_ingest_job_started(database_url: str, job_id: str) -> None:
    _update_job(
        database_url,
        job_id,
        status="running",
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def mark_ingest_job_succeeded(database_url: str, job_id: str, result_message: str) -> None:
    now = datetime.now(timezone.utc)
    _update_job(
        database_url,
        job_id,
        status="succeeded",
        result_message=result_message,
        finished_at=now,
        updated_at=now,
    )


def mark_ingest_job_failed(database_url: str, job_id: str, error_message: str) -> None:
    now = datetime.now(timezone.utc)
    _update_job(
        database_url,
        job_id,
        status="failed",
        error_message=error_message,
        finished_at=now,
        updated_at=now,
    )


def _update_job(database_url: str, job_id: str, **fields: Any) -> None:
    assignments: list[str] = []
    params: dict[str, Any] = {"job_id": job_id}
    for key, value in fields.items():
        assignments.append(f"{key} = :{key}")
        params[key] = value

    if not assignments:
        return

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                f"""
                UPDATE ingest_jobs
                SET {', '.join(assignments)}
                WHERE id = :job_id
                """
            ),
            params,
        )


def _summary_from_row(row: Any) -> IngestJobSummary:
    return IngestJobSummary(
        id=str(row["id"]),
        task_id=row["task_id"],
        source_type=str(row["source_type"]),
        job_mode=str(row["job_mode"]),
        status=str(row["status"]),
        requested_paths=_as_path_list(row["requested_paths"]),
        uploaded_file_ids=_as_str_list(row["uploaded_file_ids"]),
        result_message=row["result_message"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _detail_from_row(row: Any) -> IngestJobDetail:
    summary = _summary_from_row(row)
    return IngestJobDetail(
        **summary.__dict__,
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def _normalize_paths(requested_paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for path in requested_paths:
        value = str(path).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _as_path_list(value: Any) -> list[str]:
    return _as_str_list(value)


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(decoded, list):
            return [str(item) for item in decoded]
        return [str(decoded)]
    return [str(value)]


def _normalize_ids(uploaded_file_ids: list[str]) -> list[str]:
    normalized: list[str] = []
    for upload_id in uploaded_file_ids:
        value = str(upload_id).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _ensure_uploaded_files_exist(database_url: str, uploaded_file_ids: list[str]) -> None:
    for upload_id in uploaded_file_ids:
        get_uploaded_file(database_url, upload_id)


def _ensure_requested_inputs(requested_paths: list[str], uploaded_file_ids: list[str]) -> None:
    if requested_paths or uploaded_file_ids:
        return
    raise ValueError("At least one requested path or uploaded file is required")
