from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


FeedbackVerdict = Literal["helpful", "not_helpful", "partially_helpful"]
FeedbackReasonCode = Literal["grounding", "retrieval", "abstain", "tone", "policy", "other"]
FeedbackReviewStatus = Literal["new", "triaged", "promoted", "ignored"]


class FeedbackCreateRequest(BaseModel):
    search_query_id: str = Field(..., min_length=1, max_length=64)
    verdict: FeedbackVerdict
    reason_code: FeedbackReasonCode
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackReviewUpdateRequest(BaseModel):
    review_status: FeedbackReviewStatus
    reviewed_by: str | None = Field(default=None, max_length=120)
    promoted_eval_path: str | None = Field(default=None, max_length=500)


class FeedbackSummary(BaseModel):
    id: str
    search_query_id: str
    request_kind: str
    question: str
    verdict: FeedbackVerdict
    reason_code: FeedbackReasonCode
    issue_category: str
    review_status: FeedbackReviewStatus
    comment_preview: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class FeedbackDetail(FeedbackSummary):
    comment: str | None = None
    reviewed_by: str | None = None
    promoted_eval_path: str | None = None
    langsmith_run_id: str | None = None
