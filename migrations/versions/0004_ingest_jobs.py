from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_ingest_jobs"
down_revision = "0003_search_history_answers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=True, unique=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("job_mode", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_paths", sa.JSON(), nullable=False),
        sa.Column("result_message", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_ingest_jobs_status", "ingest_jobs", ["status"])
    op.create_index("ix_ingest_jobs_created_at", "ingest_jobs", ["created_at"])

    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False, unique=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
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
    op.create_index("ix_uploaded_files_created_at", "uploaded_files", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_uploaded_files_created_at", table_name="uploaded_files")
    op.drop_table("uploaded_files")
    op.drop_index("ix_ingest_jobs_created_at", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_status", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
