from __future__ import annotations

from src.backend.app.core.corpus_integrity import verify_corpus_integrity
from src.backend.app.core.corpus_persist import (
    count_active_corpus_rows,
    count_corpus_rows_for_job,
    count_source_document_versions,
    persist_prepared_sources,
)
from src.backend.app.core.corpus_prepare import collect_prepared_sources
from src.backend.app.core.corpus_schema import (
    CorpusIngestResult,
    CorpusIntegrityIssue,
    CorpusIntegrityReport,
    PreparedCorpusSource,
)
