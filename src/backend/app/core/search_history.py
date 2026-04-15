from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.schemas.retrieval import RetrievalMetadata
from src.backend.app.schemas.retrieval import Source


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHistorySummary:
    id: str
    request_kind: str
    question: str
    requested_mode: str
    mode_used: str
    final_k: int
    initial_k: int
    detected_year: str | None
    answer_preview: str | None
    latency_ms: int
    source_count: int
    unique_source_count: int
    warning: str | None
    created_at: datetime


@dataclass(frozen=True)
class SearchHistoryDetail(SearchHistorySummary):
    answer: str | None
    sources: list[Source]


def persist_search_history(
    database_url: str | None,
    *,
    request_kind: str,
    question: str,
    requested_mode: str,
    mode_used: str,
    retrieval: RetrievalMetadata,
    sources: list[Source],
    latency_ms: int,
    answer: str | None = None,
    warning: str | None = None,
) -> str | None:
    if not database_url:
        return None

    history_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    source_files = [source.file_name for source in sources]
    unique_source_count = len(set(source_files))
    answer_preview = _build_answer_preview(answer)

    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO search_queries (
                        id,
                        request_kind,
                        question,
                        requested_mode,
                        mode_used,
                        final_k,
                        initial_k,
                        detected_year,
                        answer,
                        answer_preview,
                        use_hybrid,
                        use_rerank,
                        latency_ms,
                        source_count,
                        unique_source_count,
                        warning,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :request_kind,
                        :question,
                        :requested_mode,
                        :mode_used,
                        :final_k,
                        :initial_k,
                        :detected_year,
                        :answer,
                        :answer_preview,
                        :use_hybrid,
                        :use_rerank,
                        :latency_ms,
                        :source_count,
                        :unique_source_count,
                        :warning,
                        :created_at,
                        :updated_at
                    )
                    """
                ),
                {
                    "id": history_id,
                    "request_kind": request_kind,
                    "question": question,
                    "requested_mode": requested_mode,
                    "mode_used": mode_used,
                    "final_k": retrieval.final_k,
                    "initial_k": retrieval.initial_k,
                    "detected_year": retrieval.detected_year,
                    "answer": answer,
                    "answer_preview": answer_preview,
                    "use_hybrid": retrieval.use_hybrid,
                    "use_rerank": retrieval.use_rerank,
                    "latency_ms": latency_ms,
                    "source_count": len(sources),
                    "unique_source_count": unique_source_count,
                    "warning": warning,
                    "created_at": now,
                    "updated_at": now,
                },
            )

            if sources:
                connection.execute(
                    text(
                        """
                        INSERT INTO search_results (
                            query_id,
                            rank,
                            file_name,
                            domain,
                            topic,
                            year,
                            page,
                            preview
                        ) VALUES (
                            :query_id,
                            :rank,
                            :file_name,
                            :domain,
                            :topic,
                            :year,
                            :page,
                            :preview
                        )
                        """
                    ),
                    [
                        {
                            "query_id": history_id,
                            "rank": source.rank,
                            "file_name": source.file_name,
                            "domain": source.domain,
                            "topic": source.topic,
                            "year": source.year,
                            "page": _normalize_page(source.page),
                            "preview": source.preview,
                        }
                        for source in sources
                    ],
                )
    except SQLAlchemyError as exc:
        logger.warning("Failed to persist search history: %s", exc)
        return None

    return history_id


def list_search_history(database_url: str | None, limit: int = 20) -> list[SearchHistorySummary]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
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
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [_summary_from_row(row) for row in rows]


def get_search_history_entry(
    database_url: str | None,
    query_id: str,
) -> SearchHistoryDetail:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            query_row = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        request_kind,
                        question,
                        requested_mode,
                        mode_used,
                        final_k,
                        initial_k,
                        detected_year,
                        answer,
                        answer_preview,
                        latency_ms,
                        source_count,
                        unique_source_count,
                        warning,
                        created_at
                    FROM search_queries
                    WHERE id = :query_id
                    """
                ),
                {"query_id": query_id},
            ).mappings().first()
            if query_row is None:
                raise KeyError(query_id)

            result_rows = connection.execute(
                text(
                    """
                    SELECT
                        rank,
                        file_name,
                        domain,
                        topic,
                        year,
                        page,
                        preview
                    FROM search_results
                    WHERE query_id = :query_id
                    ORDER BY rank ASC, id ASC
                    """
                ),
                {"query_id": query_id},
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    summary = _summary_from_row(query_row)
    return SearchHistoryDetail(
        **summary.__dict__,
        answer=query_row["answer"],
        sources=[_source_from_row(row) for row in result_rows],
    )


def _summary_from_row(row: Any) -> SearchHistorySummary:
    return SearchHistorySummary(
        id=str(row["id"]),
        request_kind=str(row["request_kind"]),
        question=str(row["question"]),
        requested_mode=str(row["requested_mode"]),
        mode_used=str(row["mode_used"]),
        final_k=int(row["final_k"]),
        initial_k=int(row["initial_k"]),
        detected_year=row["detected_year"],
        answer_preview=row["answer_preview"],
        latency_ms=int(row["latency_ms"]),
        source_count=int(row["source_count"]),
        unique_source_count=int(row["unique_source_count"]),
        warning=row["warning"],
        created_at=row["created_at"],
    )


def _source_from_row(row: Any) -> Source:
    return Source(
        rank=int(row["rank"]),
        file_name=str(row["file_name"]),
        domain=row["domain"],
        topic=row["topic"],
        year=row["year"],
        page=_restore_page(row["page"]),
        preview=str(row["preview"]),
    )


def _normalize_page(value: int | str | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _restore_page(value: Any) -> int | str | None:
    if value is None:
        return None
    text_value = str(value)
    if text_value.isdigit():
        return int(text_value)
    return text_value


def _build_answer_preview(answer: str | None, limit: int = 300) -> str | None:
    if answer is None:
        return None
    preview = answer.strip()
    if not preview:
        return None
    if len(preview) <= limit:
        return preview
    return f"{preview[: limit - 1].rstrip()}…"
