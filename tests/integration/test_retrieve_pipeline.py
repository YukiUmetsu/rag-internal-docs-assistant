from __future__ import annotations

from pathlib import Path

from src.rag.ingest import run_full_update_from_paths
from src.rag.retrieve import retrieve


def test_retrieve_dense_only_returns_relevant_refund_policy_doc(
    versioned_policy_fixture_paths: list[str],
    test_index_path: Path,
    test_chunks_path: Path,
) -> None:
    run_full_update_from_paths(
        versioned_policy_fixture_paths,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
    )

    results = retrieve(
        query="What is the refund window?",
        final_k=4,
        initial_k=8,
        max_chunks_per_source=2,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
        use_hybrid=False,
        use_rerank=False,
    )

    assert results
    assert any(doc.metadata.get("domain") == "policies" for doc in results)
    assert any(
        "refund" in doc.metadata.get("file_name", "").lower()
        for doc in results
    )


def test_retrieve_dense_only_returns_relevant_engineering_doc(
    basic_ingest_fixture_paths: list[str],
    test_index_path: Path,
    test_chunks_path: Path,
) -> None:
    run_full_update_from_paths(
        basic_ingest_fixture_paths,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
    )

    results = retrieve(
        query="How many retry attempts are allowed?",
        final_k=4,
        initial_k=8,
        max_chunks_per_source=2,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
        use_hybrid=False,
        use_rerank=False,
    )

    assert results
    assert any(
        doc.metadata.get("file_name") == "payment_flow.md"
        for doc in results
    )
    assert any(
        "retry" in doc.page_content.lower() or "attempt" in doc.page_content.lower()
        for doc in results
    )


def test_retrieve_hybrid_returns_relevant_engineering_doc_for_keyword_query(
    basic_ingest_fixture_paths: list[str],
    test_index_path: Path,
    test_chunks_path: Path,
) -> None:
    run_full_update_from_paths(
        basic_ingest_fixture_paths,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
    )

    results = retrieve(
        query="retry failed requests",
        final_k=4,
        initial_k=8,
        max_chunks_per_source=2,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
        use_hybrid=True,
        use_rerank=False,
    )

    assert results
    assert any(
        doc.metadata.get("file_name") == "payment_flow.md"
        for doc in results
    )


def test_retrieve_hybrid_with_rerank_returns_relevant_refund_doc(
    versioned_policy_fixture_paths: list[str],
    test_index_path: Path,
    test_chunks_path: Path,
) -> None:
    run_full_update_from_paths(
        versioned_policy_fixture_paths,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
    )

    results = retrieve(
        query="What is the refund window?",
        final_k=4,
        initial_k=8,
        max_chunks_per_source=2,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
        use_hybrid=True,
        use_rerank=True,
    )

    assert results
    assert any(
        "refund" in doc.metadata.get("file_name", "").lower()
        for doc in results
    )


def test_retrieve_limits_chunks_per_source_in_real_index(
    versioned_policy_fixture_paths: list[str],
    test_index_path: Path,
    test_chunks_path: Path,
) -> None:
    run_full_update_from_paths(
        versioned_policy_fixture_paths,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
    )

    results = retrieve(
        query="Tell me about refund policy approval rules and refund window",
        final_k=8,
        initial_k=12,
        max_chunks_per_source=1,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
        use_hybrid=True,
        use_rerank=True,
    )

    assert results

    source_doc_ids = [
        str(doc.metadata.get("source_doc_id", "unknown"))
        for doc in results
    ]
    assert len(source_doc_ids) == len(set(source_doc_ids))


def test_retrieve_returns_no_more_than_final_k_results(
    basic_ingest_fixture_paths: list[str],
    test_index_path: Path,
    test_chunks_path: Path,
) -> None:
    run_full_update_from_paths(
        basic_ingest_fixture_paths,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
    )

    results = retrieve(
        query="refunds and retries",
        final_k=2,
        initial_k=8,
        max_chunks_per_source=2,
        vectorstore_path=str(test_index_path),
        chunks_path=str(test_chunks_path),
        use_hybrid=True,
        use_rerank=True,
    )

    assert len(results) <= 2