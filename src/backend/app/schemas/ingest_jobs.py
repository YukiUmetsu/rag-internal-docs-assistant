from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IngestJobCreateRequest(BaseModel):
    source_type: Literal["mounted_data"] = "mounted_data"
    job_mode: Literal["validation"] = "validation"
    requested_paths: list[str] = Field(default_factory=lambda: ["data"], min_length=1)
    uploaded_file_ids: list[str] = Field(default_factory=list)


class IngestJobSummary(BaseModel):
    id: str
    task_id: str | None = None
    source_type: str
    job_mode: str
    status: Literal["queued", "running", "succeeded", "failed"]
    requested_paths: list[str]
    uploaded_file_ids: list[str] = Field(default_factory=list)
    result_message: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class IngestJobDetail(IngestJobSummary):
    started_at: datetime | None = None
    finished_at: datetime | None = None
