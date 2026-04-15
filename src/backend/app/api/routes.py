from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from src.backend.app.core.database import check_database_health
from src.backend.app.core.ingest_jobs import (
    enqueue_validation_ingest_job,
    get_ingest_job,
    list_ingest_jobs,
)
from src.backend.app.core.settings import get_settings, path_exists
from src.backend.app.core.uploads import UploadTooLargeError, store_uploaded_files
from src.backend.app.core.queue import (
    check_celery_worker_health,
    check_redis_health,
    enqueue_diagnostic_task,
    get_diagnostic_task_status,
)
from src.backend.app.core.search_history import (
    get_search_history_entry as load_search_history_entry,
    list_search_history as load_search_history,
)
from src.backend.app.schemas.chat import ChatRequest, ChatResponse
from src.backend.app.schemas.async_tasks import (
    CeleryDiagnosticRequest,
    CeleryDiagnosticSubmissionResponse,
    CeleryDiagnosticStatusResponse,
)
from src.backend.app.schemas.ingest_jobs import IngestJobCreateRequest, IngestJobDetail, IngestJobSummary
from src.backend.app.schemas.uploads import UploadedFileSummary
from src.backend.app.schemas.search_history import SearchHistoryDetail, SearchHistorySummary
from src.backend.app.schemas.retrieval import HealthResponse, RetrieveRequest, RetrieveResponse
from src.backend.app.services.rag_service import chat, retrieve_only


router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    database_health = check_database_health(settings.database_url)
    redis_health = check_redis_health(settings.redis_url)
    celery_worker_health = check_celery_worker_health()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        vectorstore_available=path_exists(settings.vectorstore_path),
        chunks_available=path_exists(settings.chunks_path),
        database_available=database_health.database_available,
        pgvector_available=database_health.pgvector_available,
        database_error=database_health.error,
        redis_available=redis_health.available,
        redis_error=redis_health.error,
        celery_worker_available=celery_worker_health.available,
        celery_worker_error=celery_worker_health.error,
        live_llm_configured=bool(settings.groq_model_name and settings.groq_api_key_present),
        groq_model_name=settings.groq_model_name,
        langsmith_tracing_enabled=settings.langsmith_tracing_enabled,
        langsmith_project=settings.langsmith_project,
    )


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_endpoint(request: RetrieveRequest) -> RetrieveResponse:
    return retrieve_only(request)


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    return chat(request)


@router.get("/search-history", response_model=list[SearchHistorySummary])
def search_history_endpoint(limit: int = Query(default=20, ge=1, le=100)) -> list[SearchHistorySummary]:
    settings = get_settings()
    try:
        history = load_search_history(settings.database_url, limit=limit)
        return [SearchHistorySummary(**item.__dict__) for item in history]
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/search-history/{query_id}", response_model=SearchHistoryDetail)
def search_history_detail_endpoint(query_id: str) -> SearchHistoryDetail:
    settings = get_settings()
    try:
        history = load_search_history_entry(settings.database_url, query_id)
        return SearchHistoryDetail(**history.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Search history entry not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/diagnostics/celery/ping", response_model=CeleryDiagnosticSubmissionResponse, status_code=202)
def enqueue_celery_ping(request: CeleryDiagnosticRequest) -> CeleryDiagnosticSubmissionResponse:
    task_id = enqueue_diagnostic_task(request.message)
    return CeleryDiagnosticSubmissionResponse(
        task_id=task_id,
        state="PENDING",
        message=request.message,
    )


@router.get("/diagnostics/celery/{task_id}", response_model=CeleryDiagnosticStatusResponse)
def get_celery_ping_status(task_id: str) -> CeleryDiagnosticStatusResponse:
    status = get_diagnostic_task_status(task_id)
    return CeleryDiagnosticStatusResponse(**status.__dict__)


@router.post("/ingest/jobs", response_model=IngestJobDetail, status_code=202)
def create_ingest_job(request: IngestJobCreateRequest) -> IngestJobDetail:
    settings = get_settings()
    try:
        job = enqueue_validation_ingest_job(
            settings.database_url,
            source_type=request.source_type,
            job_mode=request.job_mode,
            requested_paths=request.requested_paths,
            uploaded_file_ids=request.uploaded_file_ids,
        )
        return IngestJobDetail(**job.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Uploaded file not found") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ingest/uploads", response_model=list[UploadedFileSummary], status_code=201)
def upload_ingest_files(files: list[UploadFile] = File(...)) -> list[UploadedFileSummary]:
    settings = get_settings()
    try:
        _validate_upload_file_types(files)
        uploaded_files = store_uploaded_files(
            settings.database_url,
            settings.uploads_path,
            settings.max_upload_file_size_bytes,
            files,
        )
        return [UploadedFileSummary(**uploaded_file.__dict__) for uploaded_file in uploaded_files]
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ingest/jobs", response_model=list[IngestJobSummary])
def ingest_jobs_endpoint(limit: int = Query(default=20, ge=1, le=100)) -> list[IngestJobSummary]:
    settings = get_settings()
    try:
        jobs = list_ingest_jobs(settings.database_url, limit=limit)
        return [IngestJobSummary(**job.__dict__) for job in jobs]
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ingest/jobs/{job_id}", response_model=IngestJobDetail)
def ingest_job_detail_endpoint(job_id: str) -> IngestJobDetail:
    settings = get_settings()
    try:
        job = get_ingest_job(settings.database_url, job_id)
        return IngestJobDetail(**job.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ingest job not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _validate_upload_file_types(files: list[UploadFile]) -> None:
    allowed_suffixes = {".md", ".pdf"}
    invalid_files = [
        file.filename
        for file in files
        if not file.filename or not file.filename.lower().endswith(tuple(allowed_suffixes))
    ]
    if invalid_files:
        raise ValueError(f"Unsupported upload file type(s): {', '.join(invalid_files)}")
