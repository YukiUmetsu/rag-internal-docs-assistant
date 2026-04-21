from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from src.backend.app.core.ingest_jobs import IngestJobDetail, enqueue_validation_ingest_job


def test_enqueue_validation_ingest_job_returns_created_job_without_refresh() -> None:
    job = IngestJobDetail(
        id="job-123",
        task_id="job-123",
        source_type="mounted_data",
        job_mode="validation",
        status="queued",
        requested_paths=["data/policies/refund_policy_2026.md"],
        uploaded_file_ids=[],
        result_message=None,
        error_message=None,
        created_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
        updated_at=datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
        started_at=None,
        finished_at=None,
    )

    with (
        patch("src.backend.app.core.ingest_jobs.create_ingest_job", return_value=job),
        patch("src.backend.app.core.ingest_jobs.validation_ingest_job.apply_async", return_value=None),
        patch("src.backend.app.core.ingest_jobs.get_ingest_job", side_effect=AssertionError("should not refresh")),
    ):
        result = enqueue_validation_ingest_job(
            "postgresql://example",
            source_type="mounted_data",
            job_mode="validation",
            requested_paths=["data/policies/refund_policy_2026.md"],
        )

    assert result.status == "queued"
    assert result.id == "job-123"
