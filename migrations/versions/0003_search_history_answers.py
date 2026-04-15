from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_search_history_answers"
down_revision = "0002_search_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("search_queries", sa.Column("answer", sa.Text(), nullable=True))
    op.add_column("search_queries", sa.Column("answer_preview", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("search_queries", "answer_preview")
    op.drop_column("search_queries", "answer")
