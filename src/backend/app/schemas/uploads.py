from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UploadedFileSummary(BaseModel):
    id: str
    original_filename: str
    stored_path: str
    content_type: str | None = None
    file_size_bytes: int
    checksum: str
    created_at: datetime
    updated_at: datetime
