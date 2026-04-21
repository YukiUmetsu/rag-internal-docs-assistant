from __future__ import annotations

import cgi
import io
import logging
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.datastructures import UploadFile

from src.backend.app.core.settings import get_settings, path_exists
from src.backend.app.schemas.async_tasks import (
    CeleryDiagnosticRequest,
    CeleryDiagnosticSubmissionResponse,
    CeleryDiagnosticStatusResponse,
)
from src.backend.app.schemas.chat import ChatRequest, ChatResponse
from src.backend.app.schemas.feedback import FeedbackCreateRequest, FeedbackDetail
from src.backend.app.schemas.ingest_jobs import IngestJobCreateRequest, IngestJobDetail, IngestJobSummary
from src.backend.app.schemas.retrieval import HealthResponse, RetrieveRequest, RetrieveResponse
from src.backend.app.schemas.search_history import SearchHistoryDetail, SearchHistorySummary
from src.backend.app.schemas.uploads import UploadedFileSummary


router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _feedback_route_context(
    *,
    endpoint: str,
    search_query_id: str | None = None,
    verdict: str | None = None,
    reason_code: str | None = None,
) -> str:
    return (
        "endpoint=%s search_query_id=%s verdict=%s reason_code=%s"
        % (
            endpoint,
            search_query_id or "<none>",
            verdict or "<none>",
            reason_code or "<none>",
        )
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    from src.backend.app.core.database import check_database_health
    from src.backend.app.core.queue.health import check_celery_worker_health, check_redis_health

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
    from src.backend.app.core.request_ids import generate_request_id
    from src.backend.app.services.rag_service import retrieve_only

    request_id = generate_request_id()
    return retrieve_only(request, request_id=request_id, langsmith_extra={"run_id": request_id})


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    from src.backend.app.core.request_ids import generate_request_id
    from src.backend.app.services.rag_service import chat

    request_id = generate_request_id()
    return chat(request, request_id=request_id, langsmith_extra={"run_id": request_id})


@router.get("/search-history", response_model=list[SearchHistorySummary])
def search_history_endpoint(limit: int = Query(default=20, ge=1, le=100)) -> list[SearchHistorySummary]:
    settings = get_settings()
    from src.backend.app.core.search_history import list_search_history

    try:
        history = list_search_history(settings.database_url, limit=limit)
        return [SearchHistorySummary(**item.__dict__) for item in history]
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/search-history/{query_id}", response_model=SearchHistoryDetail)
def search_history_detail_endpoint(query_id: str) -> SearchHistoryDetail:
    settings = get_settings()
    from src.backend.app.core.search_history import get_search_history_entry

    try:
        history = get_search_history_entry(settings.database_url, query_id)
        return SearchHistoryDetail(**history.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Search history entry not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/feedback", response_model=FeedbackDetail, status_code=201)
def create_feedback_endpoint(request: FeedbackCreateRequest) -> FeedbackDetail:
    settings = get_settings()
    from src.backend.app.core.feedback import persist_answer_feedback

    try:
        feedback = persist_answer_feedback(
            settings.database_url,
            search_query_id=request.search_query_id,
            verdict=request.verdict,
            reason_code=request.reason_code,
            comment=request.comment,
        )
        if feedback is None:
            raise RuntimeError("Feedback persistence is unavailable")
        return FeedbackDetail(**feedback.__dict__)
    except KeyError as exc:
        logger.warning(
            "Feedback submission failed because the search history entry was missing (%s)",
            _feedback_route_context(
                endpoint="create_feedback",
                search_query_id=request.search_query_id,
                verdict=request.verdict,
                reason_code=request.reason_code,
            ),
            exc_info=True,
        )
        raise HTTPException(status_code=404, detail="Search history entry not found") from exc
    except RuntimeError as exc:
        logger.warning(
            "Feedback submission failed at the API boundary (%s): %s",
            _feedback_route_context(
                endpoint="create_feedback",
                search_query_id=request.search_query_id,
                verdict=request.verdict,
                reason_code=request.reason_code,
            ),
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/diagnostics/celery/ping", response_model=CeleryDiagnosticSubmissionResponse, status_code=202)
def enqueue_celery_ping(request: CeleryDiagnosticRequest) -> CeleryDiagnosticSubmissionResponse:
    from src.backend.app.core.queue.tasks import enqueue_diagnostic_task

    task_id = enqueue_diagnostic_task(request.message)
    return CeleryDiagnosticSubmissionResponse(
        task_id=task_id,
        state="PENDING",
        message=request.message,
    )


@router.get("/diagnostics/celery/{task_id}", response_model=CeleryDiagnosticStatusResponse)
def get_celery_ping_status(task_id: str) -> CeleryDiagnosticStatusResponse:
    from src.backend.app.core.queue.tasks import get_diagnostic_task_status

    status = get_diagnostic_task_status(task_id)
    return CeleryDiagnosticStatusResponse(**status.__dict__)


@router.post("/ingest/jobs", response_model=IngestJobDetail, status_code=202)
def create_ingest_job(request: IngestJobCreateRequest) -> IngestJobDetail:
    settings = get_settings()
    from src.backend.app.core.ingest_jobs import enqueue_document_ingest_job, enqueue_validation_ingest_job

    try:
        if request.job_mode == "validation":
            job = enqueue_validation_ingest_job(
                settings.database_url,
                source_type=request.source_type,
                job_mode=request.job_mode,
                requested_paths=request.requested_paths,
                uploaded_file_ids=request.uploaded_file_ids,
            )
        else:
            job = enqueue_document_ingest_job(
                settings.database_url,
                source_type=request.source_type,
                job_mode=request.job_mode,
                requested_paths=request.requested_paths,
                uploaded_file_ids=request.uploaded_file_ids,
            )
        return IngestJobDetail(**job.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Uploaded file not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ingest/uploads", response_model=list[UploadedFileSummary], status_code=201)
async def upload_ingest_files(request: Request) -> list[UploadedFileSummary]:
    settings = get_settings()
    from src.backend.app.core.uploads import UploadTooLargeError, store_uploaded_files

    try:
        files = await _extract_uploaded_files(request)
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
    from src.backend.app.core.ingest_jobs import list_ingest_jobs

    try:
        jobs = list_ingest_jobs(settings.database_url, limit=limit)
        return [IngestJobSummary(**job.__dict__) for job in jobs]
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ingest/jobs/{job_id}", response_model=IngestJobDetail)
def ingest_job_detail_endpoint(job_id: str) -> IngestJobDetail:
    settings = get_settings()
    from src.backend.app.core.ingest_jobs import get_ingest_job

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


async def _extract_uploaded_files(request: Request) -> list[UploadFile]:
    try:
        form = await request.form()
        files = [
            file
            for file in form.getlist("files")
            if isinstance(file, UploadFile) and file.filename
        ]
        if files:
            return files
    except (AssertionError, RuntimeError):
        pass

    body = await request.body()
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type.lower():
        return []

    environ = {
        "REQUEST_METHOD": request.method,
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(body)),
    }
    field_storage = cgi.FieldStorage(
        fp=io.BytesIO(body),
        environ=environ,
        keep_blank_values=True,
    )
    extracted_files: list[UploadFile] = []
    for item in getattr(field_storage, "list", []) or []:
        if getattr(item, "name", None) != "files":
            continue
        filename = getattr(item, "filename", None)
        if not filename:
            continue
        extracted_files.append(
            SimpleNamespace(
                filename=filename,
                file=io.BytesIO(item.file.read()),
                content_type=getattr(item, "type", None),
            )
        )
    return extracted_files
