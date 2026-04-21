from __future__ import annotations

from src.backend.app.core.corpus.integrity import verify_corpus_integrity
from src.backend.app.core.corpus.persist import (
    count_active_corpus_rows,
    count_corpus_rows_for_job,
    count_source_document_versions,
    persist_prepared_sources,
)
from src.backend.app.core.corpus.prepare import collect_prepared_sources
from src.backend.app.core.corpus.schema import (
    CorpusIngestResult,
    CorpusIntegrityIssue,
    CorpusIntegrityReport,
    PreparedCorpusSource,
)
