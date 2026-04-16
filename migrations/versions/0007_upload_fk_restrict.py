from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_upload_fk_restrict"
down_revision = "0006_source_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    constraint_name = _get_uploaded_file_fk_constraint_name(connection)
    if constraint_name is not None:
        op.drop_constraint(constraint_name, "source_documents", type_="foreignkey")

    op.create_foreign_key(
        "source_documents_uploaded_file_id_fkey",
        "source_documents",
        "uploaded_files",
        ["uploaded_file_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    connection = op.get_bind()
    constraint_name = _get_uploaded_file_fk_constraint_name(connection)
    if constraint_name is not None:
        op.drop_constraint(constraint_name, "source_documents", type_="foreignkey")

    op.create_foreign_key(
        "source_documents_uploaded_file_id_fkey",
        "source_documents",
        "uploaded_files",
        ["uploaded_file_id"],
        ["id"],
        ondelete="CASCADE",
    )


def _get_uploaded_file_fk_constraint_name(connection: sa.Connection) -> str | None:
    row = connection.execute(
        sa.text(
            """
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel
                ON rel.oid = con.conrelid
            JOIN pg_attribute att
                ON att.attrelid = rel.oid
               AND att.attnum = ANY (con.conkey)
            WHERE rel.relname = 'source_documents'
              AND att.attname = 'uploaded_file_id'
              AND con.contype = 'f'
              AND pg_get_constraintdef(con.oid) LIKE '%REFERENCES uploaded_files%'
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return str(row)
