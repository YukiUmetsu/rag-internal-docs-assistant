from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_answer_feedback"
down_revision = "0007_upload_fk_restrict"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_feedback",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "search_query_id",
            sa.String(length=36),
            sa.ForeignKey("search_queries.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("langsmith_run_id", sa.String(length=64), nullable=True),
        sa.Column("request_kind", sa.String(length=32), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        sa.Column("issue_category", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default=sa.text("'new'")),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_eval_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_answer_feedback_created_at",
        "answer_feedback",
        ["created_at"],
    )
    op.create_index(
        "ix_answer_feedback_issue_category",
        "answer_feedback",
        ["issue_category"],
    )
    op.create_index(
        "ix_answer_feedback_review_status",
        "answer_feedback",
        ["review_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_answer_feedback_review_status", table_name="answer_feedback")
    op.drop_index("ix_answer_feedback_issue_category", table_name="answer_feedback")
    op.drop_index("ix_answer_feedback_created_at", table_name="answer_feedback")
    op.drop_table("answer_feedback")
