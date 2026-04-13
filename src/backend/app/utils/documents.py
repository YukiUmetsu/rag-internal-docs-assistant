from __future__ import annotations

from langchain_core.documents import Document

from src.backend.app.schemas.retrieval import Source


def serialize_document(doc: Document, rank: int) -> Source:
    page = doc.metadata.get("page")
    return Source(
        rank=rank,
        file_name=str(doc.metadata.get("file_name", "unknown")),
        domain=_optional_str(doc.metadata.get("domain")),
        topic=_optional_str(doc.metadata.get("topic")),
        year=_optional_str(doc.metadata.get("year")),
        page=page,
        preview=doc.page_content[:500],
    )


def serialize_documents(docs: list[Document]) -> list[Source]:
    return [serialize_document(doc, rank=index) for index, doc in enumerate(docs, start=1)]


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
