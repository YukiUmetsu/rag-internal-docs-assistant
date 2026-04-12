from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from src.rag.chunk_store import save_chunks
from src.rag.hybrid_retrieve import keyword_retrieve, merge_retrieval_results


def make_doc(
    content: str,
    *,
    source_doc_id: str,
    file_name: str,
    domain: str = "",
    topic: str = "",
    year: str | None = None,
    page: int | None = None,
) -> Document:
    metadata = {
        "source_doc_id": source_doc_id,
        "file_name": file_name,
        "domain": domain,
        "topic": topic,
        "year": year,
    }
    if page is not None:
        metadata["page"] = page

    return Document(page_content=content, metadata=metadata)


def test_keyword_retrieve_returns_exact_match(tmp_path: Path) -> None:
    chunks_path = tmp_path / "chunks.jsonl"

    docs = [
        make_doc(
            "Refunds are allowed within 30 days.",
            source_doc_id="refund_2026",
            file_name="refund_policy_2026.md",
            domain="policies",
            topic="refund_policy",
            year="2026",
        ),
        make_doc(
            "The payment flow retries failed requests up to 3 times.",
            source_doc_id="payment_flow",
            file_name="payment_flow.md",
            domain="engineering",
            topic="payment_flow",
        ),
    ]
    save_chunks(docs, chunks_path)

    results = keyword_retrieve(
        query="retry failed requests",
        chunks_path=str(chunks_path),
        k=2,
    )

    assert results
    assert results[0].metadata["file_name"] == "payment_flow.md"


def test_merge_retrieval_results_deduplicates_overlap() -> None:
    shared = make_doc(
        "Refunds are allowed within 30 days.",
        source_doc_id="refund_2026",
        file_name="refund_policy_2026.md",
        domain="policies",
        topic="refund_policy",
        year="2026",
    )
    keyword_only = make_doc(
        "Refund approval rules apply for large orders.",
        source_doc_id="refund_2026",
        file_name="refund_policy_2026.md",
        domain="policies",
        topic="refund_policy",
        year="2026",
    )

    merged = merge_retrieval_results(
        dense_docs=[shared],
        keyword_docs=[shared, keyword_only],
    )

    assert len(merged) == 2


def test_merge_retrieval_results_preserves_dense_order_first() -> None:
    dense_first = make_doc(
        "Dense result A",
        source_doc_id="a",
        file_name="a.md",
    )
    dense_second = make_doc(
        "Dense result B",
        source_doc_id="b",
        file_name="b.md",
    )
    keyword_only = make_doc(
        "Keyword-only result",
        source_doc_id="c",
        file_name="c.md",
    )

    merged = merge_retrieval_results(
        dense_docs=[dense_first, dense_second],
        keyword_docs=[dense_second, keyword_only],
    )

    file_names = [doc.metadata["file_name"] for doc in merged]
    assert file_names == ["a.md", "b.md", "c.md"]