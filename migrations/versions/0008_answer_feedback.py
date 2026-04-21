from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_answer_feedback"
down_revision = "0007_upload_fk_restrict"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS answer_feedback (
            id VARCHAR(36) PRIMARY KEY,
            search_query_id VARCHAR(36) NOT NULL UNIQUE REFERENCES search_queries(id) ON DELETE CASCADE,
            langsmith_run_id VARCHAR(64),
            request_kind VARCHAR(32) NOT NULL,
            verdict VARCHAR(32) NOT NULL,
            reason_code VARCHAR(32) NOT NULL,
            issue_category VARCHAR(32) NOT NULL,
            comment TEXT,
            review_status VARCHAR(32) NOT NULL DEFAULT 'new',
            reviewed_by VARCHAR(120),
            reviewed_at TIMESTAMP WITH TIME ZONE,
            promoted_eval_path TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_answer_feedback_created_at ON answer_feedback (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_answer_feedback_issue_category ON answer_feedback (issue_category)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_answer_feedback_review_status ON answer_feedback (review_status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_answer_feedback_review_status")
    op.execute("DROP INDEX IF EXISTS ix_answer_feedback_issue_category")
    op.execute("DROP INDEX IF EXISTS ix_answer_feedback_created_at")
    op.execute("DROP TABLE IF EXISTS answer_feedback")
