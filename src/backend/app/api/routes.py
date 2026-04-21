from __future__ import annotations

import cgi
import io
import logging
from dataclasses import asdict
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile

from src.backend.app.core.admin import (
    get_admin_dashboard,
    get_admin_document,
    get_admin_retriever_backend,
    get_admin_history,
    get_admin_job,
    get_admin_upload,
    list_admin_documents,
    list_admin_history,
    list_admin_jobs,
    list_admin_uploads,
    set_admin_retriever_backend,
)
from src.backend.app.core.database import check_database_health
from src.backend.app.core.ingest_jobs import (
    enqueue_document_ingest_job,
    enqueue_validation_ingest_job,
    get_ingest_job,
    list_ingest_jobs,
)
from src.backend.app.core.request_ids import generate_request_id
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
from src.backend.app.schemas.admin import (
    AdminDashboardResponse,
    AdminDocumentResponse,
    AdminPaginatedFeedback,
    AdminPaginatedDocuments,
    AdminPaginatedHistory,
    AdminPaginatedJobs,
    AdminPaginatedUploads,
    AdminRetrieverBackendRequest,
    AdminRetrieverBackendResponse,
    AdminJobStat,
    AdminUploadStat,
)
from src.backend.app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackDetail,
    FeedbackReviewUpdateRequest,
    FeedbackReviewStatus,
    FeedbackSummary,
)
from src.backend.app.schemas.documents import SourceDocumentSummary
from src.backend.app.schemas.ingest_jobs import IngestJobCreateRequest, IngestJobDetail, IngestJobSummary
from src.backend.app.schemas.uploads import UploadedFileSummary
from src.backend.app.schemas.search_history import SearchHistoryDetail, SearchHistorySummary
from src.backend.app.schemas.retrieval import HealthResponse, RetrieveRequest, RetrieveResponse
from src.backend.app.services.rag_service import chat, retrieve_only
from src.backend.app.core.feedback import (
    list_answer_feedback,
    persist_answer_feedback,
    update_answer_feedback_review,
)


router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _feedback_route_context(
    *,
    endpoint: str,
    feedback_id: str | None = None,
    search_query_id: str | None = None,
    verdict: str | None = None,
    reason_code: str | None = None,
    review_status: str | None = None,
    reviewed_by: str | None = None,
    promoted_eval_path: str | None = None,
) -> str:
    return (
        "endpoint=%s feedback_id=%s search_query_id=%s verdict=%s reason_code=%s review_status=%s reviewed_by=%s promoted_eval_path=%s"
        % (
            endpoint,
            feedback_id or "<none>",
            search_query_id or "<none>",
            verdict or "<none>",
            reason_code or "<none>",
            review_status or "<none>",
            reviewed_by or "<none>",
            promoted_eval_path or "<none>",
        )
    )


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


@router.get("/admin/dashboard", response_model=AdminDashboardResponse)
def admin_dashboard_endpoint() -> AdminDashboardResponse:
    settings = get_settings()
    try:
        dashboard = get_admin_dashboard(settings.database_url, retriever_backend=settings.retriever_backend)
        return AdminDashboardResponse(**asdict(dashboard))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/retriever-backend", response_model=AdminRetrieverBackendResponse)
def admin_retriever_backend_endpoint() -> AdminRetrieverBackendResponse:
    settings = get_settings()
    try:
        state = get_admin_retriever_backend(settings.database_url, settings.retriever_backend)
        return AdminRetrieverBackendResponse(**asdict(state))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/admin/retriever-backend", response_model=AdminRetrieverBackendResponse)
def update_admin_retriever_backend_endpoint(
    request: AdminRetrieverBackendRequest,
) -> AdminRetrieverBackendResponse:
    settings = get_settings()
    try:
        state = set_admin_retriever_backend(settings.database_url, request.retriever_backend)
        return AdminRetrieverBackendResponse(**asdict(state))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/uploads", response_model=AdminPaginatedUploads)
def admin_uploads_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
) -> AdminPaginatedUploads:
    settings = get_settings()
    try:
        uploads, total = list_admin_uploads(
            settings.database_url,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        return AdminPaginatedUploads(
            items=[AdminUploadStat(**upload.__dict__) for upload in uploads],
            total=total,
            limit=limit,
            offset=offset,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/uploads/{upload_id}", response_model=AdminUploadStat)
def admin_upload_detail_endpoint(upload_id: str) -> AdminUploadStat:
    settings = get_settings()
    try:
        upload = get_admin_upload(settings.database_url, upload_id)
        return AdminUploadStat(**upload.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Uploaded file not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/admin/jobs", response_model=AdminPaginatedJobs)
def admin_jobs_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    days: int | None = Query(default=None, ge=1, le=3650),
) -> AdminPaginatedJobs:
    settings = get_settings()
    try:
        jobs, total = list_admin_jobs(
            settings.database_url,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            days=days,
        )
        return AdminPaginatedJobs(
            items=[AdminJobStat(**job.__dict__) for job in jobs],
            total=total,
            limit=limit,
            offset=offset,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/jobs/{job_id}", response_model=AdminJobStat)
def admin_job_detail_endpoint(job_id: str) -> AdminJobStat:
    settings = get_settings()
    try:
        job = get_admin_job(settings.database_url, job_id)
        return AdminJobStat(**job.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ingest job not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/admin/documents", response_model=AdminPaginatedDocuments)
def admin_documents_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    active_only: bool = Query(default=False),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
) -> AdminPaginatedDocuments:
    settings = get_settings()
    try:
        documents, total = list_admin_documents(
            settings.database_url,
            limit=limit,
            offset=offset,
            active_only=active_only,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        return AdminPaginatedDocuments(
            items=[SourceDocumentSummary(**document.__dict__) for document in documents],
            total=total,
            limit=limit,
            offset=offset,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/documents/{document_id}", response_model=AdminDocumentResponse)
def admin_document_detail_endpoint(document_id: str) -> AdminDocumentResponse:
    settings = get_settings()
    try:
        document = get_admin_document(settings.database_url, document_id)
        return AdminDocumentResponse(**document.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Source document not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/admin/history", response_model=AdminPaginatedHistory)
def admin_history_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
) -> AdminPaginatedHistory:
    settings = get_settings()
    try:
        history, total = list_admin_history(
            settings.database_url,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        return AdminPaginatedHistory(
            items=[SearchHistorySummary(**item) for item in history],
            total=total,
            limit=limit,
            offset=offset,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/history/{query_id}", response_model=SearchHistoryDetail)
def admin_history_detail_endpoint(query_id: str) -> SearchHistoryDetail:
    settings = get_settings()
    try:
        history = get_admin_history(settings.database_url, query_id)
        return SearchHistoryDetail(**history.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Search history entry not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_endpoint(request: RetrieveRequest) -> RetrieveResponse:
    request_id = generate_request_id()
    return retrieve_only(request, request_id=request_id, langsmith_extra={"run_id": request_id})


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    request_id = generate_request_id()
    return chat(request, request_id=request_id, langsmith_extra={"run_id": request_id})


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


@router.post("/feedback", response_model=FeedbackDetail, status_code=201)
def create_feedback_endpoint(request: FeedbackCreateRequest) -> FeedbackDetail:
    settings = get_settings()
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


@router.get("/admin/feedback", response_model=AdminPaginatedFeedback)
def admin_feedback_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    review_status: FeedbackReviewStatus | None = Query(default=None),
) -> AdminPaginatedFeedback:
    settings = get_settings()
    try:
        items, total = list_answer_feedback(
            settings.database_url,
            limit=limit,
            offset=offset,
            review_status=review_status,
        )
        return AdminPaginatedFeedback(
            items=[FeedbackSummary(**item.__dict__) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.patch("/admin/feedback/{feedback_id}", response_model=FeedbackDetail)
def update_admin_feedback_endpoint(
    feedback_id: str,
    request: FeedbackReviewUpdateRequest,
) -> FeedbackDetail:
    settings = get_settings()
    try:
        feedback = update_answer_feedback_review(
            settings.database_url,
            feedback_id,
            review_status=request.review_status,
            reviewed_by=request.reviewed_by,
            promoted_eval_path=request.promoted_eval_path,
        )
        return FeedbackDetail(**feedback.__dict__)
    except KeyError as exc:
        logger.warning(
            "Admin feedback triage failed because the feedback row was missing (%s)",
            _feedback_route_context(
                endpoint="update_admin_feedback",
                feedback_id=feedback_id,
                review_status=request.review_status,
                reviewed_by=request.reviewed_by,
                promoted_eval_path=request.promoted_eval_path,
            ),
            exc_info=True,
        )
        raise HTTPException(status_code=404, detail="Feedback entry not found") from exc
    except ValueError as exc:
        logger.warning(
            "Admin feedback triage rejected an invalid transition (%s): %s",
            _feedback_route_context(
                endpoint="update_admin_feedback",
                feedback_id=feedback_id,
                review_status=request.review_status,
                reviewed_by=request.reviewed_by,
                promoted_eval_path=request.promoted_eval_path,
            ),
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.warning(
            "Admin feedback triage failed at the API boundary (%s): %s",
            _feedback_route_context(
                endpoint="update_admin_feedback",
                feedback_id=feedback_id,
                review_status=request.review_status,
                reviewed_by=request.reviewed_by,
                promoted_eval_path=request.promoted_eval_path,
            ),
            exc,
            exc_info=True,
        )
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
