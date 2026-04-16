from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SourceDocumentSummary(BaseModel):
    id: str
    source_kind: Literal["mounted_data", "uploaded_files"]
    display_name: str
    source_path: str | None = None
    uploaded_file_id: str | None = None
    ingest_job_id: str | None = None
    domain: str | None = None
    topic: str | None = None
    year: int | None = None
    content_type: str | None = None
    file_size_bytes: int | None = None
    checksum: str
    is_active: bool
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    ingested_at: datetime | None = None


class SourceDocumentDetail(SourceDocumentSummary):
    total_chunk_count: int

