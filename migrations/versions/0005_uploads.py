from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_uploads"
down_revision = "0004_ingest_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "uploaded_files",
        "file_size",
        new_column_name="file_size_bytes",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
    )
    op.drop_constraint("uploaded_files_checksum_key", "uploaded_files", type_="unique")
    op.create_index("ix_uploaded_files_original_filename", "uploaded_files", ["original_filename"])
    op.create_index("ix_uploaded_files_checksum", "uploaded_files", ["checksum"])

    op.create_table(
        "ingest_job_uploads",
        sa.Column(
            "ingest_job_id",
            sa.String(length=36),
            sa.ForeignKey("ingest_jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "uploaded_file_id",
            sa.String(length=36),
            sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_ingest_job_uploads_ingest_job_id",
        "ingest_job_uploads",
        ["ingest_job_id"],
    )
    op.create_index(
        "ix_ingest_job_uploads_uploaded_file_id",
        "ingest_job_uploads",
        ["uploaded_file_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingest_job_uploads_uploaded_file_id", table_name="ingest_job_uploads")
    op.drop_index("ix_ingest_job_uploads_ingest_job_id", table_name="ingest_job_uploads")
    op.drop_table("ingest_job_uploads")

    op.drop_index("ix_uploaded_files_checksum", table_name="uploaded_files")
    op.drop_index("ix_uploaded_files_original_filename", table_name="uploaded_files")
    op.create_unique_constraint(
        "uploaded_files_checksum_key",
        "uploaded_files",
        ["checksum"],
    )
    op.alter_column(
        "uploaded_files",
        "file_size_bytes",
        new_column_name="file_size",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
    )
