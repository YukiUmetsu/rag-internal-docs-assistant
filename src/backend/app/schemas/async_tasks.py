from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CeleryDiagnosticRequest(BaseModel):
    message: str = Field(default="pong", min_length=1, max_length=200)


class CeleryDiagnosticSubmissionResponse(BaseModel):
    task_id: str
    state: Literal["PENDING"]
    message: str


class CeleryDiagnosticStatusResponse(BaseModel):
    task_id: str
    state: str
    ready: bool
    result: dict[str, Any] | str | None = None
    traceback: str | None = None
