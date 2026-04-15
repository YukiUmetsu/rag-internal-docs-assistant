from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_search_history"
down_revision = "0001_enable_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_queries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_kind", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("requested_mode", sa.String(length=32), nullable=False),
        sa.Column("mode_used", sa.String(length=32), nullable=False),
        sa.Column("final_k", sa.Integer(), nullable=False),
        sa.Column("initial_k", sa.Integer(), nullable=False),
        sa.Column("detected_year", sa.String(length=32), nullable=True),
        sa.Column("use_hybrid", sa.Boolean(), nullable=False),
        sa.Column("use_rerank", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("unique_source_count", sa.Integer(), nullable=False),
        sa.Column("warning", sa.Text(), nullable=True),
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
        "ix_search_queries_created_at",
        "search_queries",
        ["created_at"],
    )
    op.create_index(
        "ix_search_queries_request_kind",
        "search_queries",
        ["request_kind"],
    )

    op.create_table(
        "search_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "query_id",
            sa.String(length=36),
            sa.ForeignKey("search_queries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("year", sa.Text(), nullable=True),
        sa.Column("page", sa.Text(), nullable=True),
        sa.Column("preview", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_search_results_query_id_rank",
        "search_results",
        ["query_id", "rank"],
    )


def downgrade() -> None:
    op.drop_index("ix_search_results_query_id_rank", table_name="search_results")
    op.drop_table("search_results")
    op.drop_index("ix_search_queries_request_kind", table_name="search_queries")
    op.drop_index("ix_search_queries_created_at", table_name="search_queries")
    op.drop_table("search_queries")
