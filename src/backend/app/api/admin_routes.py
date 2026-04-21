from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from src.backend.app.core.settings import get_settings
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
    FeedbackDetail,
    FeedbackReviewUpdateRequest,
    FeedbackReviewStatus,
    FeedbackSummary,
)
from src.backend.app.schemas.documents import SourceDocumentSummary
from src.backend.app.schemas.search_history import SearchHistoryDetail, SearchHistorySummary


router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _feedback_route_context(
    *,
    endpoint: str,
    feedback_id: str | None = None,
    review_status: str | None = None,
    reviewed_by: str | None = None,
    promoted_eval_path: str | None = None,
) -> str:
    return (
        "endpoint=%s feedback_id=%s review_status=%s reviewed_by=%s promoted_eval_path=%s"
        % (
            endpoint,
            feedback_id or "<none>",
            review_status or "<none>",
            reviewed_by or "<none>",
            promoted_eval_path or "<none>",
        )
    )


@router.get("/admin/dashboard", response_model=AdminDashboardResponse)
def admin_dashboard_endpoint() -> AdminDashboardResponse:
    settings = get_settings()
    from src.backend.app.core.admin import get_admin_dashboard

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
    from src.backend.app.core.admin import get_admin_retriever_backend

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
    from src.backend.app.core.admin import set_admin_retriever_backend

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
    from src.backend.app.core.admin import list_admin_uploads

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
    from src.backend.app.core.admin import get_admin_upload

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
    from src.backend.app.core.admin import list_admin_jobs

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
    from src.backend.app.core.admin import get_admin_job

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
    from src.backend.app.core.admin import list_admin_documents

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
    from src.backend.app.core.admin import get_admin_document

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
    from src.backend.app.core.admin import list_admin_history

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
    from src.backend.app.core.admin import get_admin_history

    try:
        history = get_admin_history(settings.database_url, query_id)
        return SearchHistoryDetail(**history.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Search history entry not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/admin/feedback", response_model=AdminPaginatedFeedback)
def admin_feedback_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    review_status: FeedbackReviewStatus | None = Query(default=None),
) -> AdminPaginatedFeedback:
    settings = get_settings()
    from src.backend.app.core.feedback import list_answer_feedback

    try:
        items, total = list_answer_feedback(
            settings.database_url,
            limit=limit,
            offset=offset,
            review_status=review_status,  # type: ignore[arg-type]
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
    from src.backend.app.core.feedback import update_answer_feedback_review

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
