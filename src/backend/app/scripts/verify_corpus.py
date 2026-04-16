from __future__ import annotations

import sys

from src.backend.app.core.corpus import verify_corpus_integrity
from src.backend.app.core.settings import get_settings


def main() -> None:
    settings = get_settings()
    report = verify_corpus_integrity(settings.database_url)

    print(f"active_source_documents={report.active_source_documents}")
    print(f"active_document_chunks={report.active_document_chunks}")
    print(f"orphan_chunk_count={report.orphan_chunk_count}")
    print(f"source_documents_without_chunks={report.source_documents_without_chunks}")
    print(f"documents_with_missing_files={report.documents_with_missing_files}")

    if not report.is_healthy:
        for issue in report.issues:
            print(f"{issue.code}: {issue.message}", file=sys.stderr)
        raise SystemExit(1)

    print("Corpus integrity check passed.")


if __name__ == "__main__":
    main()
