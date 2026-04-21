from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.core.documents import (
    SourceDocumentDetail,
    SourceDocumentSummary,
    count_source_documents,
    get_source_document,
    list_source_documents,
)
from src.backend.app.core.ingest_jobs import get_ingest_job
from src.backend.app.core.search_history import get_search_history_entry
from src.backend.app.core.uploads import get_uploaded_file
from src.rag.retriever_backend import (
    RetrieverBackend,
    get_retriever_backend_override,
    resolve_retriever_backend,
    set_retriever_backend_override,
)


@dataclass(frozen=True)
class AdminMetric:
    label: str
    value: str
    detail: str


@dataclass(frozen=True)
class AdminSeriesPoint:
    label: str
    value: float


@dataclass(frozen=True)
class AdminQuestionStat:
    question: str
    count: int
    last_asked_at: datetime
    avg_latency_ms: float


@dataclass(frozen=True)
class AdminJobStat:
    id: str
    source_type: str
    job_mode: str
    status: str
    summary: str
    started_at: datetime | None
    finished_at: datetime | None
    source_documents: int
    chunks: int
    task_id: str | None


@dataclass(frozen=True)
class AdminUploadStat:
    id: str
    filename: str
    size_bytes: int
    checksum: str
    job_id: str | None
    created_at: datetime


@dataclass(frozen=True)
class AdminHealthFlag:
    label: str
    value: str


@dataclass(frozen=True)
class AdminCorpusStatus:
    status: str
    active_documents: int
    active_chunks: int
    orphan_chunks: int
    documents_without_chunks: int
    documents_with_missing_files: int


@dataclass(frozen=True)
class AdminDashboardSnapshot:
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
    latest_query: str | None
    latest_ingest_at: datetime | None
    latest_failed_ingest_at: datetime | None


@dataclass(frozen=True)
class AdminRetrieverBackendState:
    retriever_backend: str
    override_enabled: bool


UPLOAD_SORT_COLUMNS: dict[str, str] = {
    "filename": "uploaded_files.original_filename",
    "size": "uploaded_files.file_size_bytes",
    "checksum": "uploaded_files.checksum",
    "job_id": "job_id",
    "created_at": "uploaded_files.created_at",
}

JOB_SORT_COLUMNS: dict[str, str] = {
    "id": "ingest_jobs.id",
    "source_type": "ingest_jobs.source_type",
    "job_mode": "ingest_jobs.job_mode",
    "status": "ingest_jobs.status",
    "started_at": "COALESCE(ingest_jobs.started_at, ingest_jobs.created_at)",
    "finished_at": "ingest_jobs.finished_at",
    "source_documents": "COALESCE(corpus_counts.source_documents_count, 0)",
    "chunks": "COALESCE(corpus_counts.document_chunks_count, 0)",
    "created_at": "ingest_jobs.created_at",
}

DOCUMENT_SORT_COLUMNS: dict[str, str] = {
    "display_name": "source_documents.display_name",
    "source_kind": "source_kind",
    "domain": "source_documents.domain",
    "topic": "source_documents.topic",
    "year": "source_documents.year",
    "chunk_count": "COALESCE(chunk_counts.chunk_count, 0)",
    "created_at": "source_documents.created_at",
    "updated_at": "source_documents.updated_at",
    "ingested_at": "source_documents.ingested_at",
    "checksum": "source_documents.checksum",
}

HISTORY_SORT_COLUMNS: dict[str, str] = {
    "question": "search_queries.question",
    "requested_mode": "search_queries.requested_mode",
    "mode_used": "search_queries.mode_used",
    "final_k": "search_queries.final_k",
    "initial_k": "search_queries.initial_k",
    "latency_ms": "search_queries.latency_ms",
    "source_count": "search_queries.source_count",
    "unique_source_count": "search_queries.unique_source_count",
    "created_at": "search_queries.created_at",
}


def get_admin_dashboard(
    database_url: str | None,
    *,
    retriever_backend: str,
    recent_limit: int = 3,
) -> AdminDashboardSnapshot:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    from src.backend.app.core.corpus import count_active_corpus_rows, verify_corpus_integrity

    backend_state = get_admin_retriever_backend(database_url, retriever_backend)
    corpus_report = verify_corpus_integrity(database_url)
    active_corpus = count_active_corpus_rows(database_url)
    search_stats = _get_search_activity_stats(database_url)
    recent_jobs = _list_recent_jobs(database_url, limit=recent_limit)
    recent_uploads = _list_recent_uploads(database_url, limit=recent_limit)
    top_questions_week = _get_top_questions(database_url, since_days=7, limit=3)
    top_questions_month = _get_top_questions(database_url, since_days=30, limit=4)

    return AdminDashboardSnapshot(
        retriever_backend=backend_state.retriever_backend,
        corpus=AdminCorpusStatus(
            status=_corpus_status(corpus_report),
            active_documents=corpus_report.active_source_documents,
            active_chunks=corpus_report.active_document_chunks,
            orphan_chunks=corpus_report.orphan_chunk_count,
            documents_without_chunks=corpus_report.source_documents_without_chunks,
            documents_with_missing_files=corpus_report.documents_with_missing_files,
        ),
        metrics=_build_metrics(active_corpus, search_stats, backend_state.retriever_backend),
        search_volume=_build_daily_search_series(database_url, days=7),
        latency_series=_build_daily_latency_series(database_url, days=7),
        ingest_series=_build_daily_ingest_series(database_url, days=7),
        top_questions_week=top_questions_week,
        top_questions_month=top_questions_month,
        recent_jobs=recent_jobs,
        recent_uploads=recent_uploads,
        health_flags=_build_health_flags(corpus_report),
        latest_query=_get_latest_query(database_url),
        latest_ingest_at=_get_latest_ingest_time(database_url),
        latest_failed_ingest_at=_get_latest_failed_ingest_time(database_url),
    )


def get_admin_retriever_backend(database_url: str | None, default_backend: str) -> AdminRetrieverBackendState:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    override = get_retriever_backend_override(database_url)
    if override is not None:
        return AdminRetrieverBackendState(retriever_backend=override.value, override_enabled=True)

    backend = resolve_retriever_backend(default_backend)
    return AdminRetrieverBackendState(retriever_backend=backend.value, override_enabled=False)


def set_admin_retriever_backend(database_url: str | None, backend: str) -> AdminRetrieverBackendState:
    resolved = set_retriever_backend_override(database_url, backend)
    return AdminRetrieverBackendState(retriever_backend=resolved.value, override_enabled=True)


def _build_order_clause(
    sort_by: str,
    sort_dir: str,
    *,
    allowed_columns: dict[str, str],
    default_sort_by: str,
    tie_breaker: str,
) -> str:
    normalized_sort_by = (sort_by or default_sort_by).strip().lower()
    if normalized_sort_by not in allowed_columns:
        allowed = ", ".join(sorted(allowed_columns))
        raise ValueError(f"sort_by must be one of: {allowed}")

    normalized_sort_dir = (sort_dir or "desc").strip().lower()
    if normalized_sort_dir not in {"asc", "desc"}:
        raise ValueError("sort_dir must be asc or desc")

    return f"{allowed_columns[normalized_sort_by]} {normalized_sort_dir.upper()} NULLS LAST, {tie_breaker}"


def list_admin_uploads(
    database_url: str | None,
    *,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[AdminUploadStat], int]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    order_clause = _build_order_clause(
        sort_by,
        sort_dir,
        allowed_columns=UPLOAD_SORT_COLUMNS,
        default_sort_by="created_at",
        tie_breaker="uploaded_files.id DESC",
    )
    try:
        with engine.connect() as connection:
            total = int(connection.execute(text("SELECT COUNT(*) FROM uploaded_files")).scalar_one())
            rows = connection.execute(
                text(
                    f"""
                    SELECT
                        uploaded_files.id,
                        uploaded_files.original_filename,
                        uploaded_files.file_size_bytes,
                        uploaded_files.checksum,
                        uploaded_files.created_at,
                        latest_job.ingest_job_id AS job_id
                    FROM uploaded_files
                    LEFT JOIN LATERAL (
                        SELECT ingest_job_uploads.ingest_job_id
                        FROM ingest_job_uploads
                        WHERE ingest_job_uploads.uploaded_file_id = uploaded_files.id
                        ORDER BY ingest_job_uploads.created_at DESC
                        LIMIT 1
                        ) AS latest_job ON true
                    ORDER BY {order_clause}
                    LIMIT :limit
                    OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [_upload_stat_from_row(row) for row in rows], total


def get_admin_upload(database_url: str | None, upload_id: str) -> AdminUploadStat:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    upload = get_uploaded_file(database_url, upload_id)
    return AdminUploadStat(
        id=upload.id,
        filename=upload.original_filename,
        size_bytes=upload.file_size_bytes,
        checksum=upload.checksum,
        job_id=_get_latest_upload_job_id(database_url, upload_id),
        created_at=upload.created_at,
    )


def list_admin_jobs(
    database_url: str | None,
    *,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    days: int | None = None,
) -> tuple[list[AdminJobStat], int]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    order_clause = _build_order_clause(
        sort_by,
        sort_dir,
        allowed_columns=JOB_SORT_COLUMNS,
        default_sort_by="created_at",
        tie_breaker="ingest_jobs.id DESC",
    )
    since = None
    if days is not None:
        if days < 1:
            raise ValueError("days must be greater than or equal to 1")
        since = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        with engine.connect() as connection:
            total_query = """
                SELECT COUNT(*)
                FROM ingest_jobs
                {where_clause}
            """
            where_clause = "WHERE ingest_jobs.created_at >= :since" if since is not None else ""
            total = int(
                connection.execute(
                    text(total_query.format(where_clause=where_clause)),
                    {"since": since} if since is not None else {},
                ).scalar_one()
            )
            rows = connection.execute(
                text(
                    f"""
                    SELECT
                        ingest_jobs.id,
                        ingest_jobs.task_id,
                        ingest_jobs.source_type,
                        ingest_jobs.job_mode,
                        ingest_jobs.status,
                        COALESCE(ingest_jobs.result_message, ingest_jobs.error_message, 'Queued for processing.') AS summary,
                        COALESCE(ingest_jobs.started_at, ingest_jobs.created_at) AS started_at,
                        ingest_jobs.finished_at,
                        COALESCE(corpus_counts.source_documents_count, 0) AS source_documents,
                        COALESCE(corpus_counts.document_chunks_count, 0) AS chunks
                    FROM ingest_jobs
                    LEFT JOIN (
                        SELECT
                            source_documents.ingest_job_id AS ingest_job_id,
                            COUNT(DISTINCT source_documents.id) AS source_documents_count,
                            COUNT(document_chunks.id) AS document_chunks_count
                        FROM source_documents
                        LEFT JOIN document_chunks
                            ON document_chunks.source_document_id = source_documents.id
                        GROUP BY source_documents.ingest_job_id
                    ) AS corpus_counts
                        ON corpus_counts.ingest_job_id = ingest_jobs.id
                    {where_clause}
                    ORDER BY {order_clause}
                    LIMIT :limit
                    OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset, "since": since} if since is not None else {"limit": limit, "offset": offset},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [_job_stat_from_row(row) for row in rows], total


def get_admin_job(database_url: str | None, job_id: str) -> AdminJobStat:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    job = get_ingest_job(database_url, job_id)
    counts = _get_job_corpus_counts(database_url, job_id)
    summary = job.result_message or job.error_message or "Queued for processing."
    return AdminJobStat(
        id=job.id,
        source_type=job.source_type,
        job_mode=job.job_mode,
        status=job.status,
        summary=summary,
        started_at=job.started_at,
        finished_at=job.finished_at,
        source_documents=counts["source_documents_count"],
        chunks=counts["document_chunks_count"],
        task_id=job.task_id,
    )


def list_admin_documents(
    database_url: str | None,
    *,
    limit: int = 20,
    offset: int = 0,
    active_only: bool = False,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[SourceDocumentSummary], int]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    order_clause = _build_order_clause(
        sort_by,
        sort_dir,
        allowed_columns=DOCUMENT_SORT_COLUMNS,
        default_sort_by="created_at",
        tie_breaker="source_documents.id DESC",
    )
    try:
        with engine.connect() as connection:
            total = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM source_documents
                        WHERE (:active_only = false OR source_documents.is_active = true)
                        """
                    ),
                    {"active_only": active_only},
                ).scalar_one()
            )
            rows = connection.execute(
                text(
                    f"""
                    SELECT
                        source_documents.id,
                        CASE
                            WHEN source_documents.uploaded_file_id IS NULL THEN 'mounted_data'
                            ELSE 'uploaded_files'
                        END AS source_kind,
                        source_documents.display_name,
                        source_documents.source_path,
                        source_documents.uploaded_file_id,
                        source_documents.ingest_job_id,
                        source_documents.domain,
                        source_documents.topic,
                        source_documents.year,
                        source_documents.content_type,
                        source_documents.file_size_bytes,
                        source_documents.checksum,
                        source_documents.is_active,
                        COALESCE(chunk_counts.chunk_count, 0) AS chunk_count,
                        source_documents.created_at,
                        source_documents.updated_at,
                        source_documents.ingested_at
                    FROM source_documents
                    LEFT JOIN (
                        SELECT
                            source_document_id,
                            COUNT(*) AS chunk_count
                        FROM document_chunks
                        GROUP BY source_document_id
                    ) AS chunk_counts
                        ON chunk_counts.source_document_id = source_documents.id
                    WHERE (:active_only = false OR source_documents.is_active = true)
                    ORDER BY {order_clause}
                    LIMIT :limit
                    OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset, "active_only": active_only},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [_summary_from_document_row(row) for row in rows], total


def get_admin_document(database_url: str | None, document_id: str) -> SourceDocumentDetail:
    return get_source_document(database_url, document_id)


def list_admin_history(
    database_url: str | None,
    *,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[Any], int]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    order_clause = _build_order_clause(
        sort_by,
        sort_dir,
        allowed_columns=HISTORY_SORT_COLUMNS,
        default_sort_by="created_at",
        tie_breaker="search_queries.id DESC",
    )
    try:
        with engine.connect() as connection:
            total = int(connection.execute(text("SELECT COUNT(*) FROM search_queries")).scalar_one())
            rows = connection.execute(
                text(
                    f"""
                    SELECT
                        id,
                        request_kind,
                        question,
                        requested_mode,
                        mode_used,
                        final_k,
                        initial_k,
                        detected_year,
                        answer_preview,
                        latency_ms,
                        source_count,
                        unique_source_count,
                        warning,
                        created_at
                    FROM search_queries
                    ORDER BY {order_clause}
                    LIMIT :limit
                    OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [row for row in rows], total


def get_admin_history(database_url: str | None, query_id: str) -> Any:
    return get_search_history_entry(database_url, query_id)


def _summary_from_document_row(row: dict[str, Any]) -> SourceDocumentSummary:
    return SourceDocumentSummary(
        id=str(row["id"]),
        source_kind=str(row["source_kind"]),
        display_name=str(row["display_name"]),
        source_path=row["source_path"],
        uploaded_file_id=row["uploaded_file_id"],
        ingest_job_id=row["ingest_job_id"],
        domain=row["domain"],
        topic=row["topic"],
        year=row["year"],
        content_type=row["content_type"],
        file_size_bytes=row["file_size_bytes"],
        checksum=str(row["checksum"]),
        is_active=bool(row["is_active"]),
        chunk_count=int(row["chunk_count"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        ingested_at=row["ingested_at"],
    )


def _build_metrics(
    corpus_rows: dict[str, int],
    search_stats: dict[str, Any],
    retriever_backend: str,
) -> list[AdminMetric]:
    active_documents = corpus_rows["source_documents"]
    active_chunks = corpus_rows["document_chunks"]
    searches_this_week = search_stats["searches_this_week"]
    average_latency_seconds = search_stats["average_latency_seconds"]
    prior_week_searches = search_stats["searches_previous_week"]
    search_growth = _percent_change(searches_this_week, prior_week_searches)
    docs_per_chunk = (active_chunks / active_documents) if active_documents else 0.0

    return [
        AdminMetric(
            label="Active documents",
            value=f"{active_documents:,}",
            detail=(
                f"+{search_stats['new_documents_this_week']:,} from the last 7 days"
                if search_stats["new_documents_this_week"] > 0
                else "No new documents in the last 7 days"
            ),
        ),
        AdminMetric(
            label="Active chunks",
            value=f"{active_chunks:,}",
            detail=f"Average {docs_per_chunk:.1f} chunks per doc" if active_documents else "No active documents",
        ),
        AdminMetric(
            label="Searches this week",
            value=f"{searches_this_week:,}",
            detail=f"{search_growth:+.0f}% vs prior week" if prior_week_searches else "No prior-week comparison",
        ),
        AdminMetric(
            label="Avg retrieval latency",
            value=f"{average_latency_seconds:.1f} s",
            detail=f"{retriever_backend.title()} backend" if retriever_backend else "Backend unavailable",
        ),
    ]


def _build_health_flags(report: Any) -> list[AdminHealthFlag]:
    return [
        AdminHealthFlag(label="Orphan chunks", value=str(report.orphan_chunk_count)),
        AdminHealthFlag(label="Docs without chunks", value=str(report.source_documents_without_chunks)),
        AdminHealthFlag(label="Missing uploads", value=str(report.documents_with_missing_files)),
        AdminHealthFlag(label="Failed jobs", value=str(_count_failed_jobs())),
    ]


def _corpus_status(report: Any) -> str:
    if report.issues:
        issue_codes = {issue.code for issue in report.issues}
        non_ingest_codes = issue_codes - {"no_active_source_documents", "no_active_document_chunks"}
        if non_ingest_codes:
            return "broken"
        return "needs_ingest"
    return "healthy"


def _get_search_activity_stats(database_url: str) -> dict[str, Any]:
    engine = create_engine(database_url, pool_pre_ping=True)
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    previous_week_start = now - timedelta(days=14)
    try:
        with engine.connect() as connection:
            searches_this_week = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM search_queries
                        WHERE created_at >= :week_start
                        """
                    ),
                    {"week_start": week_start},
                ).scalar_one()
            )
            searches_previous_week = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM search_queries
                        WHERE created_at >= :previous_week_start
                          AND created_at < :week_start
                        """
                    ),
                    {"previous_week_start": previous_week_start, "week_start": week_start},
                ).scalar_one()
            )
            average_latency_seconds = float(
                connection.execute(
                    text(
                        """
                        SELECT COALESCE(AVG(latency_ms), 0) / 1000.0
                        FROM search_queries
                        WHERE created_at >= :week_start
                        """
                    ),
                    {"week_start": week_start},
                ).scalar_one()
            )
            new_documents_this_week = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM source_documents
                        WHERE created_at >= :week_start
                        """
                    ),
                    {"week_start": week_start},
                ).scalar_one()
            )
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return {
        "searches_this_week": searches_this_week,
        "searches_previous_week": searches_previous_week,
        "average_latency_seconds": average_latency_seconds,
        "new_documents_this_week": new_documents_this_week,
    }


def _build_daily_search_series(database_url: str, *, days: int) -> list[AdminSeriesPoint]:
    return _build_daily_series(
        database_url,
        days=days,
        query="""
            SELECT
                DATE(created_at AT TIME ZONE 'UTC') AS day,
                COUNT(*) AS value
            FROM search_queries
            WHERE created_at >= :since
            GROUP BY 1
            ORDER BY 1
        """,
    )


def _build_daily_latency_series(database_url: str, *, days: int) -> list[AdminSeriesPoint]:
    return _build_daily_series(
        database_url,
        days=days,
        query="""
            SELECT
                DATE(created_at AT TIME ZONE 'UTC') AS day,
                COALESCE(AVG(latency_ms), 0) / 1000.0 AS value
            FROM search_queries
            WHERE created_at >= :since
            GROUP BY 1
            ORDER BY 1
        """,
    )


def _build_daily_ingest_series(database_url: str, *, days: int) -> list[AdminSeriesPoint]:
    return _build_daily_series(
        database_url,
        days=days,
        query="""
            SELECT
                DATE(created_at AT TIME ZONE 'UTC') AS day,
                COUNT(*) AS value
            FROM ingest_jobs
            WHERE created_at >= :since
            GROUP BY 1
            ORDER BY 1
        """,
    )


def _build_daily_series(database_url: str, *, days: int, query: str) -> list[AdminSeriesPoint]:
    engine = create_engine(database_url, pool_pre_ping=True)
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    series_dates = [start + timedelta(days=index) for index in range(days)]
    try:
        with engine.connect() as connection:
            rows = connection.execute(text(query), {"since": datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)}).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    row_map = {
        _row_day(row["day"]): float(row["value"])
        for row in rows
    }
    return [AdminSeriesPoint(label=day.strftime("%a"), value=row_map.get(day, 0.0)) for day in series_dates]


def _get_top_questions(database_url: str, *, since_days: int, limit: int) -> list[AdminQuestionStat]:
    engine = create_engine(database_url, pool_pre_ping=True)
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        question,
                        COUNT(*) AS count,
                        MAX(created_at) AS last_asked_at,
                        COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
                    FROM search_queries
                    WHERE created_at >= :since
                    GROUP BY question
                    ORDER BY count DESC, last_asked_at DESC, question ASC
                    LIMIT :limit
                    """
                ),
                {"since": since, "limit": limit},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [
        AdminQuestionStat(
            question=str(row["question"]),
            count=int(row["count"]),
            last_asked_at=row["last_asked_at"],
            avg_latency_ms=float(row["avg_latency_ms"]),
        )
        for row in rows
    ]


def _list_recent_jobs(database_url: str, *, limit: int) -> list[AdminJobStat]:
    jobs, _ = list_admin_jobs(database_url, limit=limit, offset=0)
    return jobs


def _list_recent_uploads(database_url: str, *, limit: int) -> list[AdminUploadStat]:
    uploads, _ = list_admin_uploads(database_url, limit=limit, offset=0)
    return uploads


def _get_latest_query(database_url: str) -> str | None:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT question
                    FROM search_queries
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """
                )
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return None if row is None else str(row["question"])


def _get_latest_ingest_time(database_url: str) -> datetime | None:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT finished_at
                    FROM ingest_jobs
                    WHERE status = 'succeeded' AND finished_at IS NOT NULL
                    ORDER BY finished_at DESC, id DESC
                    LIMIT 1
                    """
                )
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return None if row is None else row["finished_at"]


def _get_latest_failed_ingest_time(database_url: str) -> datetime | None:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT finished_at
                    FROM ingest_jobs
                    WHERE status = 'failed' AND finished_at IS NOT NULL
                    ORDER BY finished_at DESC, id DESC
                    LIMIT 1
                    """
                )
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return None if row is None else row["finished_at"]


def _get_latest_upload_job_id(database_url: str, upload_id: str) -> str | None:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT ingest_job_id
                    FROM ingest_job_uploads
                    WHERE uploaded_file_id = :upload_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"upload_id": upload_id},
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return None if row is None else str(row["ingest_job_id"])


def _get_job_corpus_counts(database_url: str, job_id: str) -> dict[str, int]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        COUNT(DISTINCT source_documents.id) AS source_documents_count,
                        COUNT(document_chunks.id) AS document_chunks_count
                    FROM source_documents
                    LEFT JOIN document_chunks
                        ON document_chunks.source_document_id = source_documents.id
                    WHERE source_documents.ingest_job_id = :job_id
                    """
                ),
                {"job_id": job_id},
            ).mappings().first()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    if row is None:
        return {"source_documents_count": 0, "document_chunks_count": 0}

    return {
        "source_documents_count": int(row["source_documents_count"]),
        "document_chunks_count": int(row["document_chunks_count"]),
    }


def _count_failed_jobs() -> int:
    return _count_jobs_by_status("failed")


def _count_jobs_by_status(status: str) -> int:
    from src.backend.app.core.settings import get_settings

    database_url = get_settings().database_url
    if not database_url:
        return 0

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM ingest_jobs
                    WHERE status = :status
                    """
                ),
                {"status": status},
            ).scalar_one()
    except SQLAlchemyError:
        return 0
    return int(row)


def _build_health_flags(report: Any) -> list[AdminHealthFlag]:
    return [
        AdminHealthFlag(label="Orphan chunks", value=str(report.orphan_chunk_count)),
        AdminHealthFlag(label="Docs without chunks", value=str(report.source_documents_without_chunks)),
        AdminHealthFlag(label="Missing uploads", value=str(report.documents_with_missing_files)),
        AdminHealthFlag(label="Failed jobs", value=str(_count_failed_jobs())),
    ]


def _corpus_status(report: Any) -> str:
    if report.issues:
        issue_codes = {issue.code for issue in report.issues}
        non_ingest_codes = issue_codes - {"no_active_source_documents", "no_active_document_chunks"}
        if non_ingest_codes:
            return "broken"
        return "needs_ingest"
    return "healthy"


def _percent_change(current: int, previous: int) -> float:
    if previous <= 0:
        return 0.0
    return ((current - previous) / previous) * 100.0


def _row_day(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _build_health_flags_from_counts(report: Any) -> list[AdminHealthFlag]:
    return [
        AdminHealthFlag(label="Orphan chunks", value=str(report.orphan_chunk_count)),
        AdminHealthFlag(label="Docs without chunks", value=str(report.source_documents_without_chunks)),
        AdminHealthFlag(label="Missing uploads", value=str(report.documents_with_missing_files)),
        AdminHealthFlag(label="Failed jobs", value=str(_count_failed_jobs())),
    ]


def _build_health_flags(report: Any) -> list[AdminHealthFlag]:
    return _build_health_flags_from_counts(report)


def _upload_stat_from_row(row: dict[str, Any]) -> AdminUploadStat:
    return AdminUploadStat(
        id=str(row["id"]),
        filename=str(row["original_filename"]),
        size_bytes=int(row["file_size_bytes"]),
        checksum=str(row["checksum"]),
        job_id=None if row.get("job_id") is None else str(row["job_id"]),
        created_at=row["created_at"],
    )


def _job_stat_from_row(row: dict[str, Any]) -> AdminJobStat:
    return AdminJobStat(
        id=str(row["id"]),
        source_type=str(row["source_type"]),
        job_mode=str(row["job_mode"]),
        status=str(row["status"]),
        summary=str(row["summary"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        source_documents=int(row["source_documents"]),
        chunks=int(row["chunks"]),
        task_id=None if row.get("task_id") is None else str(row["task_id"]),
    )
