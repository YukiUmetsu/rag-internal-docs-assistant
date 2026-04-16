from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from src.backend.app.schemas.documents import SourceDocumentDetail, SourceDocumentSummary
from src.backend.app.schemas.ingest_jobs import IngestJobSummary
from src.backend.app.schemas.search_history import SearchHistorySummary


class AdminMetric(BaseModel):
    label: str
    value: str
    detail: str


class AdminSeriesPoint(BaseModel):
    label: str
    value: float


class AdminQuestionStat(BaseModel):
    question: str
    count: int
    last_asked_at: datetime
    avg_latency_ms: float


class AdminJobStat(BaseModel):
    id: str
    source_type: str
    job_mode: str
    status: str
    summary: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    source_documents: int
    chunks: int
    task_id: str | None = None


class AdminUploadStat(BaseModel):
    id: str
    filename: str
    size_bytes: int
    checksum: str
    job_id: str | None = None
    created_at: datetime


class AdminHealthFlag(BaseModel):
    label: str
    value: str


class AdminCorpusStatus(BaseModel):
    status: Literal["healthy", "needs_ingest", "broken"]
    active_documents: int
    active_chunks: int
    orphan_chunks: int
    documents_without_chunks: int
    documents_with_missing_files: int


class AdminDashboardResponse(BaseModel):
    retriever_backend: str
    corpus: AdminCorpusStatus
    metrics: list[AdminMetric]
    search_volume: list[AdminSeriesPoint]
    latency_series: list[AdminSeriesPoint]
    ingest_series: list[AdminSeriesPoint]
    top_questions_week: list[AdminQuestionStat]
    top_questions_month: list[AdminQuestionStat]
    recent_jobs: list[AdminJobStat]
    recent_uploads: list[AdminUploadStat]
    health_flags: list[AdminHealthFlag]
    latest_query: str | None = None
    latest_ingest_at: datetime | None = None
    latest_failed_ingest_at: datetime | None = None


class AdminRetrieverBackendRequest(BaseModel):
    retriever_backend: Literal["faiss", "postgres"]


class AdminRetrieverBackendResponse(BaseModel):
    retriever_backend: Literal["faiss", "postgres"]
    override_enabled: bool


class AdminPaginatedUploads(BaseModel):
    items: list[AdminUploadStat]
    total: int
    limit: int
    offset: int


class AdminPaginatedJobs(BaseModel):
    items: list[AdminJobStat]
    total: int
    limit: int
    offset: int


class AdminPaginatedDocuments(BaseModel):
    items: list[SourceDocumentSummary]
    total: int
    limit: int
    offset: int


class AdminPaginatedHistory(BaseModel):
    items: list[SearchHistorySummary]
    total: int
    limit: int
    offset: int


AdminPaginatedSearchHistory = AdminPaginatedHistory


class AdminDocumentStatistics(BaseModel):
    active_documents: int
    active_chunks: int
    orphan_chunks: int
    documents_without_chunks: int


class AdminDocumentResponse(SourceDocumentDetail):
    pass
