from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.schemas.feedback import (
    FeedbackDetail,
    FeedbackReasonCode,
    FeedbackReviewStatus,
    FeedbackVerdict,
)


logger = logging.getLogger(__name__)

ISSUE_CATEGORY_BY_REASON_CODE: dict[FeedbackReasonCode, str] = {
    "grounding": "grounding",
    "retrieval": "retrieval",
    "abstain": "abstain",
    "tone": "tone",
    "policy": "policy",
    "other": "other",
}

ALLOWED_REVIEW_TRANSITIONS: dict[str, set[str]] = {
    "new": {"triaged", "promoted", "ignored"},
    "triaged": {"new", "promoted", "ignored"},
    "promoted": {"new"},
    "ignored": {"new"},
}

REVIEW_STATUS_PRIORITY: dict[str, int] = {
    "new": 0,
    "promoted": 1,
    "triaged": 2,
    "ignored": 3,
}


@dataclass(frozen=True)
class FeedbackSummary:
    id: str
    search_query_id: str
    request_kind: str
    question: str
    verdict: FeedbackVerdict
    reason_code: FeedbackReasonCode
    issue_category: str
    review_status: FeedbackReviewStatus
    comment_preview: str | None
    created_at: datetime
    reviewed_at: datetime | None


@dataclass(frozen=True)
class FeedbackDetail(FeedbackSummary):
    comment: str | None
    reviewed_by: str | None
    promoted_eval_path: str | None
    langsmith_run_id: str | None


def _feedback_context(
    *,
    search_query_id: str,
    verdict: FeedbackVerdict,
    reason_code: FeedbackReasonCode,
    review_status: FeedbackReviewStatus,
    langsmith_run_id: str | None,
) -> str:
    return (
        "search_query_id=%s verdict=%s reason_code=%s review_status=%s langsmith_run_id=%s"
        % (search_query_id, verdict, reason_code, review_status, langsmith_run_id or "<default>")
    )


def _feedback_review_context(
    *,
    feedback_id: str,
    review_status: FeedbackReviewStatus,
    reviewed_by: str | None,
    promoted_eval_path: str | None,
) -> str:
    return (
        "feedback_id=%s review_status=%s reviewed_by=%s promoted_eval_path=%s"
        % (
            feedback_id,
            review_status,
            reviewed_by or "<none>",
            promoted_eval_path or "<none>",
        )
    )


def _review_transition_context(
    *,
    feedback_id: str,
    current_status: str,
    next_status: FeedbackReviewStatus,
    reviewed_by: str | None,
    promoted_eval_path: str | None,
) -> str:
    return (
        "feedback_id=%s current_status=%s next_status=%s reviewed_by=%s promoted_eval_path=%s"
        % (
            feedback_id,
            current_status,
            next_status,
            reviewed_by or "<none>",
            promoted_eval_path or "<none>",
        )
    )


def _load_search_history_row(connection: Connection, search_query_id: str) -> dict[str, Any]:
    row = connection.execute(
        text(
            """
            SELECT request_kind, question
            FROM search_queries
            WHERE id = :search_query_id
            """
        ),
        {"search_query_id": search_query_id},
    ).mappings().first()
    if row is None:
        raise KeyError(search_query_id)
    return dict(row)


def _load_existing_feedback_row(connection: Connection, search_query_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        text(
            """
            SELECT
                id,
                request_kind,
                verdict,
                reason_code,
                issue_category,
                comment,
                review_status,
                reviewed_by,
                reviewed_at,
                promoted_eval_path,
                created_at,
                langsmith_run_id
            FROM answer_feedback
            WHERE search_query_id = :search_query_id
            """
        ),
        {"search_query_id": search_query_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def _load_feedback_detail_row(connection: Connection, feedback_id: str) -> dict[str, Any]:
    row = connection.execute(
        text(
            """
            SELECT
                af.id,
                af.search_query_id,
                af.langsmith_run_id,
                af.request_kind,
                sq.question,
                af.verdict,
                af.reason_code,
                af.issue_category,
                af.review_status,
                CASE
                    WHEN af.comment IS NULL THEN NULL
                    WHEN length(af.comment) <= 300 THEN af.comment
                    ELSE substr(af.comment, 1, 299) || '…'
                END AS comment_preview,
                af.comment,
                af.reviewed_by,
                af.reviewed_at,
                af.promoted_eval_path,
                af.created_at,
                af.updated_at
            FROM answer_feedback af
            JOIN search_queries sq ON sq.id = af.search_query_id
            WHERE af.id = :feedback_id
            """
        ),
        {"feedback_id": feedback_id},
    ).mappings().first()
    if row is None:
        raise KeyError(feedback_id)
    return dict(row)


def _insert_feedback_row(
    connection: Connection,
    *,
    feedback_id: str,
    search_query_id: str,
    request_kind: str,
    verdict: FeedbackVerdict,
    reason_code: FeedbackReasonCode,
    issue_category: str,
    comment: str | None,
    review_status: FeedbackReviewStatus,
    reviewed_by: str | None,
    promoted_eval_path: str | None,
    now: datetime,
    langsmith_run_id: str | None,
) -> None:
    logger.debug(
        "Inserting answer feedback (%s)",
        _feedback_context(
            search_query_id=search_query_id,
            verdict=verdict,
            reason_code=reason_code,
            review_status=review_status,
            langsmith_run_id=langsmith_run_id,
        ),
    )
    connection.execute(
        text(
            """
            INSERT INTO answer_feedback (
                id,
                search_query_id,
                langsmith_run_id,
                request_kind,
                verdict,
                reason_code,
                issue_category,
                comment,
                review_status,
                reviewed_by,
                reviewed_at,
                promoted_eval_path,
                created_at,
                updated_at
            ) VALUES (
                :id,
                :search_query_id,
                :langsmith_run_id,
                :request_kind,
                :verdict,
                :reason_code,
                :issue_category,
                :comment,
                :review_status,
                :reviewed_by,
                :reviewed_at,
                :promoted_eval_path,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": feedback_id,
            "search_query_id": search_query_id,
            "langsmith_run_id": langsmith_run_id or search_query_id,
            "request_kind": request_kind,
            "verdict": verdict,
            "reason_code": reason_code,
            "issue_category": issue_category,
            "comment": comment,
            "review_status": review_status,
            "reviewed_by": reviewed_by,
            "reviewed_at": now if reviewed_by else None,
            "promoted_eval_path": promoted_eval_path,
            "created_at": now,
            "updated_at": now,
        },
    )


def _build_feedback_detail(
    *,
    feedback_id: str,
    search_query_id: str,
    request_row: dict[str, Any],
    verdict: FeedbackVerdict,
    reason_code: FeedbackReasonCode,
    issue_category: str,
    comment: str | None,
    review_status: FeedbackReviewStatus,
    reviewed_by: str | None,
    reviewed_at: datetime | None,
    promoted_eval_path: str | None,
    created_at: datetime,
    langsmith_run_id: str | None,
) -> FeedbackDetail:
    summary = FeedbackSummary(
        id=feedback_id,
        search_query_id=search_query_id,
        request_kind=str(request_row["request_kind"]),
        question=str(request_row["question"]),
        verdict=verdict,
        reason_code=reason_code,
        issue_category=issue_category,
        review_status=review_status,
        comment_preview=_build_comment_preview(comment),
        created_at=created_at,
        reviewed_at=reviewed_at,
    )
    return FeedbackDetail(
        **summary.__dict__,
        comment=comment,
        reviewed_by=reviewed_by,
        promoted_eval_path=promoted_eval_path,
        langsmith_run_id=langsmith_run_id or search_query_id,
    )


def _build_comment_preview(comment: str | None) -> str | None:
    if comment is None:
        return None
    if len(comment) <= 300:
        return comment
    return comment[:299] + "…"


def persist_answer_feedback(
    database_url: str | None,
    *,
    search_query_id: str,
    verdict: FeedbackVerdict,
    reason_code: FeedbackReasonCode,
    comment: str | None = None,
    review_status: FeedbackReviewStatus = "new",
    reviewed_by: str | None = None,
    promoted_eval_path: str | None = None,
    langsmith_run_id: str | None = None,
) -> FeedbackDetail | None:
    if not database_url:
        return None

    now = datetime.now(timezone.utc)
    issue_category = ISSUE_CATEGORY_BY_REASON_CODE[reason_code]
    logger.debug(
        "Persisting answer feedback request (%s)",
        _feedback_context(
            search_query_id=search_query_id,
            verdict=verdict,
            reason_code=reason_code,
            review_status=review_status,
            langsmith_run_id=langsmith_run_id,
        ),
    )

    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.begin() as connection:
            request_row = _load_search_history_row(connection, search_query_id)
            logger.debug(
                "Loaded search history row for answer feedback (%s request_kind=%s)",
                search_query_id,
                request_row["request_kind"],
            )

            existing_row = _load_existing_feedback_row(connection, search_query_id)

            if existing_row is None:
                feedback_id = str(uuid.uuid4())
                logger.debug("Creating new answer feedback row id=%s", feedback_id)
                _insert_feedback_row(
                    connection,
                    feedback_id=feedback_id,
                    search_query_id=search_query_id,
                    request_kind=request_row["request_kind"],
                    verdict=verdict,
                    reason_code=reason_code,
                    issue_category=issue_category,
                    comment=comment,
                    review_status=review_status,
                    reviewed_by=reviewed_by,
                    promoted_eval_path=promoted_eval_path,
                    now=now,
                    langsmith_run_id=langsmith_run_id,
                )
                detail = _build_feedback_detail(
                    feedback_id=feedback_id,
                    search_query_id=search_query_id,
                    request_row=request_row,
                    verdict=verdict,
                    reason_code=reason_code,
                    issue_category=issue_category,
                    comment=comment,
                    review_status=review_status,
                    reviewed_by=reviewed_by,
                    reviewed_at=now if reviewed_by else None,
                    promoted_eval_path=promoted_eval_path,
                    created_at=now,
                    langsmith_run_id=langsmith_run_id,
                )
            else:
                feedback_id = str(existing_row["id"])
                logger.debug("Feedback already exists for search_query_id=%s, returning existing row", search_query_id)
                detail = _build_feedback_detail(
                    feedback_id=feedback_id,
                    search_query_id=search_query_id,
                    request_row=request_row,
                    verdict=str(existing_row["verdict"]),
                    reason_code=str(existing_row["reason_code"]),
                    issue_category=str(existing_row["issue_category"]),
                    comment=existing_row["comment"],
                    review_status=str(existing_row["review_status"]),
                    reviewed_by=existing_row["reviewed_by"],
                    reviewed_at=existing_row["reviewed_at"],
                    promoted_eval_path=existing_row["promoted_eval_path"],
                    created_at=existing_row["created_at"],
                    langsmith_run_id=str(existing_row.get("langsmith_run_id", search_query_id)),
                )
            logger.debug(
                "Persisted answer feedback successfully (%s feedback_id=%s)",
                _feedback_context(
                    search_query_id=search_query_id,
                    verdict=verdict,
                    reason_code=reason_code,
                    review_status=review_status,
                    langsmith_run_id=langsmith_run_id,
                ),
                feedback_id,
            )
    except SQLAlchemyError as exc:
        logger.warning(
            "Failed to persist answer feedback (%s): %s",
            _feedback_context(
                search_query_id=search_query_id,
                verdict=verdict,
                reason_code=reason_code,
                review_status=review_status,
                langsmith_run_id=langsmith_run_id,
            ),
            exc,
            exc_info=True,
        )
        return None

    return detail


def list_answer_feedback(
    database_url: str | None,
    *,
    limit: int = 20,
    offset: int = 0,
    review_status: FeedbackReviewStatus | None = None,
) -> tuple[list[FeedbackSummary], int]:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    where_clause = "WHERE 1 = 1"
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if review_status is not None:
        where_clause += " AND af.review_status = :review_status"
        params["review_status"] = review_status

    try:
        with engine.connect() as connection:
            count_row = connection.execute(
                text(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM answer_feedback af
                    {where_clause}
                    """
                ),
                params,
            ).mappings().first()
            total = int(count_row["count"]) if count_row else 0

            rows = connection.execute(
                text(
                    f"""
                    SELECT
                        af.id,
                        af.search_query_id,
                        af.request_kind,
                        sq.question,
                        af.verdict,
                        af.reason_code,
                        af.issue_category,
                        af.review_status,
                        CASE
                            WHEN af.comment IS NULL THEN NULL
                            WHEN length(af.comment) <= 300 THEN af.comment
                            ELSE substr(af.comment, 1, 299) || '…'
                        END AS comment_preview,
                        af.created_at,
                        af.reviewed_at
                    FROM answer_feedback af
                    JOIN search_queries sq ON sq.id = af.search_query_id
                    {where_clause}
                    ORDER BY
                        CASE af.review_status
                            WHEN 'new' THEN 0
                            WHEN 'promoted' THEN 1
                            WHEN 'triaged' THEN 2
                            WHEN 'ignored' THEN 3
                            ELSE 4
                        END,
                        af.created_at DESC,
                        af.id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    return [_summary_from_row(row) for row in rows], total


def get_answer_feedback_entry(database_url: str | None, feedback_id: str) -> FeedbackDetail:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = _load_feedback_detail_row(connection, feedback_id)
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    summary = _summary_from_row(row)
    return FeedbackDetail(
        **summary.__dict__,
        comment=row["comment"],
        reviewed_by=row["reviewed_by"],
        promoted_eval_path=row["promoted_eval_path"],
        langsmith_run_id=row["langsmith_run_id"],
    )


def update_answer_feedback_review(
    database_url: str | None,
    feedback_id: str,
    *,
    review_status: FeedbackReviewStatus,
    reviewed_by: str | None = None,
    promoted_eval_path: str | None = None,
) -> FeedbackDetail:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    now = datetime.now(timezone.utc)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            current_row = _load_feedback_detail_row(connection, feedback_id)
            current_status = str(current_row["review_status"])
            if review_status not in ALLOWED_REVIEW_TRANSITIONS.get(current_status, set()):
                logger.warning(
                    "Rejected invalid feedback review transition (%s)",
                    _review_transition_context(
                        feedback_id=feedback_id,
                        current_status=current_status,
                        next_status=review_status,
                        reviewed_by=reviewed_by,
                        promoted_eval_path=promoted_eval_path,
                    ),
                )
                raise ValueError(
                    f"Cannot transition feedback review status from {current_status} to {review_status}"
                )
            updated = connection.execute(
                text(
                    """
                    UPDATE answer_feedback
                    SET
                        review_status = :review_status,
                        reviewed_by = :reviewed_by,
                        reviewed_at = :reviewed_at,
                        promoted_eval_path = :promoted_eval_path,
                        updated_at = :updated_at
                    WHERE id = :feedback_id
                    """
                ),
                {
                    "feedback_id": feedback_id,
                    "review_status": review_status,
                    "reviewed_by": reviewed_by,
                    "reviewed_at": now if reviewed_by or review_status != "new" else None,
                    "promoted_eval_path": promoted_eval_path,
                    "updated_at": now,
                },
            )
            if updated.rowcount == 0:
                logger.warning(
                    "Answer feedback review update missed row (%s)",
                    _feedback_review_context(
                        feedback_id=feedback_id,
                        review_status=review_status,
                        reviewed_by=reviewed_by,
                        promoted_eval_path=promoted_eval_path,
                    ),
                )
                raise KeyError(feedback_id)
            row = _load_feedback_detail_row(connection, feedback_id)
            logger.debug(
                "Updated answer feedback review successfully (%s)",
                _feedback_review_context(
                    feedback_id=feedback_id,
                    review_status=review_status,
                    reviewed_by=reviewed_by,
                    promoted_eval_path=promoted_eval_path,
                ),
            )
    except KeyError as exc:
        logger.warning(
            "Failed to update answer feedback review because the row was not found (%s)",
            _feedback_review_context(
                feedback_id=feedback_id,
                review_status=review_status,
                reviewed_by=reviewed_by,
                promoted_eval_path=promoted_eval_path,
            ),
            exc_info=True,
        )
        raise
    except ValueError as exc:
        logger.warning(
            "Failed to update answer feedback review because the transition was invalid (%s): %s",
            _review_transition_context(
                feedback_id=feedback_id,
                current_status=current_status,
                next_status=review_status,
                reviewed_by=reviewed_by,
                promoted_eval_path=promoted_eval_path,
            ),
            exc,
            exc_info=True,
        )
        raise
    except SQLAlchemyError as exc:
        logger.warning(
            "Failed to update answer feedback review (%s): %s",
            _feedback_review_context(
                feedback_id=feedback_id,
                review_status=review_status,
                reviewed_by=reviewed_by,
                promoted_eval_path=promoted_eval_path,
            ),
            exc,
            exc_info=True,
        )
        raise RuntimeError(str(exc)) from exc

    summary = _summary_from_row(row)
    return FeedbackDetail(
        **summary.__dict__,
        comment=row["comment"],
        reviewed_by=row["reviewed_by"],
        promoted_eval_path=row["promoted_eval_path"],
        langsmith_run_id=row["langsmith_run_id"],
    )


def _summary_from_row(row: Any) -> FeedbackSummary:
    return FeedbackSummary(
        id=str(row["id"]),
        search_query_id=str(row["search_query_id"]),
        request_kind=str(row["request_kind"]),
        question=str(row["question"]),
        verdict=str(row["verdict"]),
        reason_code=str(row["reason_code"]),
        issue_category=str(row["issue_category"]),
        review_status=str(row["review_status"]),
        comment_preview=row["comment_preview"],
        created_at=row["created_at"],
        reviewed_at=row["reviewed_at"],
    )
