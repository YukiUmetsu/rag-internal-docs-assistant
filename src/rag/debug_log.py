from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from langchain_core.documents import Document


def reset_debug_log(path: str | Path) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")


def serialize_doc(doc: Document, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "source_doc_id": doc.metadata.get("source_doc_id"),
        "file_name": doc.metadata.get("file_name"),
        "chunk_id": doc.metadata.get("chunk_id"),
        "domain": doc.metadata.get("domain"),
        "topic": doc.metadata.get("topic"),
        "year": doc.metadata.get("year"),
        "preview": doc.page_content[:300],
    }


def append_rerank_debug_log(
    *,
    path: str | Path,
    query_id: str | None,
    query: str,
    mode_name: str | None,
    stage: str,
    docs: Sequence[Document],
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "query_id": query_id,
        "query": query,
        "mode": mode_name,
        "stage": stage,  # "before_rerank" | "after_rerank"
        "docs": [serialize_doc(doc, rank=i) for i, doc in enumerate(docs, start=1)],
    }

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")