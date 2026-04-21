from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.core.corpus_schema import CorpusIntegrityIssue, CorpusIntegrityReport
from src.backend.app.core.uploads import get_uploaded_file


@dataclass(frozen=True)
class _IntegrityCounts:
    active_source_documents: int
    active_document_chunks: int
    orphan_chunk_count: int
    source_documents_without_chunks: int


def verify_corpus_integrity(database_url: str | None) -> CorpusIntegrityReport:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        with engine.connect() as connection:
            counts, active_document_rows = _load_integrity_counts_and_active_rows(connection)
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    issues = _collect_missing_file_issues(database_url, active_document_rows)
    issues.extend(_collect_count_based_issues(counts))

    return CorpusIntegrityReport(
        active_source_documents=counts.active_source_documents,
        active_document_chunks=counts.active_document_chunks,
        orphan_chunk_count=counts.orphan_chunk_count,
        source_documents_without_chunks=counts.source_documents_without_chunks,
        documents_with_missing_files=_count_missing_document_file_issues(issues),
        issues=issues,
    )


def _load_integrity_counts_and_active_rows(connection) -> tuple[_IntegrityCounts, list[dict[str, object]]]:
    active_source_documents = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM source_documents
                WHERE is_active = true
                """
            )
        ).scalar_one()
    )
    active_document_chunks = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM document_chunks
                JOIN source_documents
                    ON source_documents.id = document_chunks.source_document_id
                WHERE source_documents.is_active = true
                """
            )
        ).scalar_one()
    )
    orphan_chunk_count = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM document_chunks
                LEFT JOIN source_documents
                    ON source_documents.id = document_chunks.source_document_id
                WHERE source_documents.id IS NULL
                """
            )
        ).scalar_one()
    )
    source_documents_without_chunks = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT source_documents.id
                    FROM source_documents
                    LEFT JOIN document_chunks
                        ON document_chunks.source_document_id = source_documents.id
                    WHERE source_documents.is_active = true
                    GROUP BY source_documents.id
                    HAVING COUNT(document_chunks.id) = 0
                ) AS missing_chunks
                """
            )
        ).scalar_one()
    )
    missing_file_rows = connection.execute(
        text(
            """
            SELECT
                source_documents.id,
                source_documents.display_name,
                source_documents.uploaded_file_id,
                source_documents.source_path
            FROM source_documents
            WHERE source_documents.is_active = true
            """
        )
    ).mappings().all()

    return (
        _IntegrityCounts(
            active_source_documents=active_source_documents,
            active_document_chunks=active_document_chunks,
            orphan_chunk_count=orphan_chunk_count,
            source_documents_without_chunks=source_documents_without_chunks,
        ),
        [dict(row) for row in missing_file_rows],
    )


def _collect_missing_file_issues(
    database_url: str,
    active_document_rows: list[dict[str, object]],
) -> list[CorpusIntegrityIssue]:
    # Inspect each active document row individually so the report names the
    # exact document that references a missing upload or missing source file.
    issues: list[CorpusIntegrityIssue] = []
    for row in active_document_rows:
        issues.extend(_file_issues_for_active_document_row(database_url, row))
    return issues


def _file_issues_for_active_document_row(database_url: str, row: dict[str, object]) -> list[CorpusIntegrityIssue]:
    issues: list[CorpusIntegrityIssue] = []
    uploaded_file_id = row["uploaded_file_id"]
    source_path = row["source_path"]

    if uploaded_file_id is not None:
        try:
            get_uploaded_file(database_url, str(uploaded_file_id))
        except KeyError:
            issues.append(
                CorpusIntegrityIssue(
                    code="missing_uploaded_file",
                    message=f"Active document {row['display_name']} references missing upload {uploaded_file_id}",
                )
            )

    if source_path is not None and not Path(str(source_path)).exists():
        issues.append(
            CorpusIntegrityIssue(
                code="missing_source_path",
                message=f"Active document {row['display_name']} points to missing file {source_path}",
            )
        )

    return issues


def _collect_count_based_issues(counts: _IntegrityCounts) -> list[CorpusIntegrityIssue]:
    # These checks operate on table-wide counts instead of per-row document
    # lookups, so they summarize the overall corpus health.
    issues: list[CorpusIntegrityIssue] = []
    if counts.active_source_documents == 0:
        issues.append(
            CorpusIntegrityIssue(
                code="no_active_source_documents",
                message="No active source documents are available",
            )
        )
    if counts.active_document_chunks == 0:
        issues.append(
            CorpusIntegrityIssue(
                code="no_active_document_chunks",
                message="No active document chunks are available",
            )
        )
    if counts.orphan_chunk_count > 0:
        issues.append(
            CorpusIntegrityIssue(
                code="orphan_chunks",
                message=f"Found {counts.orphan_chunk_count} chunk(s) without a source document",
            )
        )
    if counts.source_documents_without_chunks > 0:
        issues.append(
            CorpusIntegrityIssue(
                code="source_documents_without_chunks",
                message=f"Found {counts.source_documents_without_chunks} active source document(s) without chunks",
            )
    )
    return issues


def _count_missing_document_file_issues(issues: list[CorpusIntegrityIssue]) -> int:
    return len([issue for issue in issues if issue.code in {"missing_uploaded_file", "missing_source_path"}])
