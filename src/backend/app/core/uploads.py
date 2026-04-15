from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from fastapi import UploadFile
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError


@dataclass(frozen=True)
class UploadedFileSummary:
    id: str
    original_filename: str
    stored_path: str
    content_type: str | None
    file_size_bytes: int
    checksum: str
    created_at: datetime
    updated_at: datetime


UploadedFileDetail = UploadedFileSummary


def store_uploaded_files(
    database_url: str | None,
    uploads_path: str,
    max_upload_file_size_bytes: int,
    files: Iterable[UploadFile],
) -> list[UploadedFileSummary]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    uploads_root = Path(uploads_path)
    uploads_root.mkdir(parents=True, exist_ok=True)

    staged_files: list[dict[str, Any]] = []
    final_paths: list[Path] = []
    try:
        for upload_file in files:
            staged_files.append(
                _stage_single_file(
                    uploads_root,
                    upload_file,
                    max_upload_file_size_bytes=max_upload_file_size_bytes,
                )
            )
        for staged_file in staged_files:
            staged_file["temp_path"].replace(staged_file["final_path"])
            final_paths.append(staged_file["final_path"])
        stored_files = _insert_uploaded_file_rows(database_url, staged_files)
    except Exception:
        for path in final_paths:
            path.unlink(missing_ok=True)
        for staged_file in staged_files:
            temp_path = staged_file.get("temp_path")
            if isinstance(temp_path, Path):
                temp_path.unlink(missing_ok=True)
        raise
    return stored_files


def list_uploaded_files(database_url: str | None, limit: int = 20) -> list[UploadedFileSummary]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        original_filename,
                        stored_path,
                        content_type,
                        file_size_bytes,
                        checksum,
                        created_at,
                        updated_at
                    FROM uploaded_files
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [_summary_from_row(row) for row in rows]


def get_uploaded_file(database_url: str | None, upload_id: str) -> UploadedFileSummary:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        original_filename,
                        stored_path,
                        content_type,
                        file_size_bytes,
                        checksum,
                        created_at,
                        updated_at
                    FROM uploaded_files
                    WHERE id = :upload_id
                    """
                ),
                {"upload_id": upload_id},
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    if row is None:
        raise KeyError(upload_id)

    return _summary_from_row(row)


def get_uploaded_file_ids_for_job(database_url: str | None, job_id: str) -> list[str]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        COALESCE(
                            array_agg(ingest_job_uploads.uploaded_file_id),
                            ARRAY[]::text[]
                        ) AS uploaded_file_ids
                    FROM ingest_job_uploads
                    WHERE ingest_job_uploads.ingest_job_id = :job_id
                    """
                ),
                {"job_id": job_id},
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    if row is None:
        return []

    return _as_str_list(row["uploaded_file_ids"])


def link_uploaded_files_to_ingest_job(
    database_url: str | None,
    job_id: str,
    uploaded_file_ids: Iterable[str],
) -> None:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    normalized_ids = _normalize_ids(uploaded_file_ids)
    if not normalized_ids:
        return

    now = datetime.now(timezone.utc)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            _insert_ingest_job_upload_links(connection, job_id, normalized_ids, now)
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc


def _stage_single_file(
    uploads_root: Path,
    upload_file: UploadFile,
    *,
    max_upload_file_size_bytes: int,
) -> dict[str, Any]:
    if not upload_file.filename:
        raise ValueError("Uploaded files must have a filename")

    original_filename = Path(upload_file.filename).name
    upload_id = str(uuid.uuid4())
    final_path = uploads_root / f"{upload_id}_{original_filename}"
    temp_path = uploads_root / f".{upload_id}_{original_filename}.part"
    checksum = hashlib.sha256()
    file_size_bytes = 0

    with temp_path.open("wb") as destination:
        while True:
            chunk = upload_file.file.read(1024 * 1024)
            if not chunk:
                break
            file_size_bytes += len(chunk)
            if file_size_bytes > max_upload_file_size_bytes:
                temp_path.unlink(missing_ok=True)
                raise UploadTooLargeError(
                    f"Upload exceeds the maximum allowed size of {max_upload_file_size_bytes} bytes"
                )
            destination.write(chunk)
            checksum.update(chunk)

    now = datetime.now(timezone.utc)
    return {
        "id": upload_id,
        "original_filename": original_filename,
        "stored_path": str(final_path),
        "content_type": upload_file.content_type,
        "file_size_bytes": file_size_bytes,
        "checksum": checksum.hexdigest(),
        "created_at": now,
        "updated_at": now,
        "temp_path": temp_path,
        "final_path": final_path,
    }


def _insert_uploaded_file_rows(
    database_url: str | None,
    staged_files: list[dict[str, Any]],
) -> list[UploadedFileSummary]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            for staged_file in staged_files:
                connection.execute(
                    text(
                        """
                        INSERT INTO uploaded_files (
                            id,
                            original_filename,
                            stored_path,
                            content_type,
                            file_size_bytes,
                            checksum,
                            created_at,
                            updated_at
                        ) VALUES (
                            :id,
                            :original_filename,
                            :stored_path,
                            :content_type,
                            :file_size_bytes,
                            :checksum,
                            :created_at,
                            :updated_at
                        )
                        """
                    ),
                    {
                        "id": staged_file["id"],
                        "original_filename": staged_file["original_filename"],
                        "stored_path": staged_file["stored_path"],
                        "content_type": staged_file["content_type"],
                        "file_size_bytes": staged_file["file_size_bytes"],
                        "checksum": staged_file["checksum"],
                        "created_at": staged_file["created_at"],
                        "updated_at": staged_file["updated_at"],
                    },
                )
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [
        UploadedFileSummary(
            id=str(staged_file["id"]),
            original_filename=str(staged_file["original_filename"]),
            stored_path=str(staged_file["stored_path"]),
            content_type=staged_file["content_type"],
            file_size_bytes=int(staged_file["file_size_bytes"]),
            checksum=str(staged_file["checksum"]),
            created_at=staged_file["created_at"],
            updated_at=staged_file["updated_at"],
        )
        for staged_file in staged_files
    ]


def _insert_ingest_job_upload_links(
    connection: Connection,
    job_id: str,
    uploaded_file_ids: Iterable[str],
    created_at: datetime,
) -> None:
    for upload_id in uploaded_file_ids:
        connection.execute(
            text(
                """
                INSERT INTO ingest_job_uploads (
                    ingest_job_id,
                    uploaded_file_id,
                    created_at
                ) VALUES (
                    :ingest_job_id,
                    :uploaded_file_id,
                    :created_at
                )
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "ingest_job_id": job_id,
                "uploaded_file_id": upload_id,
                "created_at": created_at,
            },
        )


class UploadTooLargeError(ValueError):
    pass


def _summary_from_row(row: Any) -> UploadedFileSummary:
    return UploadedFileSummary(
        id=str(row["id"]),
        original_filename=str(row["original_filename"]),
        stored_path=str(row["stored_path"]),
        content_type=row["content_type"],
        file_size_bytes=int(row["file_size_bytes"]),
        checksum=str(row["checksum"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _normalize_ids(uploaded_file_ids: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for upload_id in uploaded_file_ids:
        value = str(upload_id).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, tuple):
        return [str(item) for item in value if item is not None]
    return [str(value)]
