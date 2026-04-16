from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.rag import retrieve as retrieve_mod
from tests.utils.fake_vectorstore import FakeVectorStore


def _docs_that_miss_query() -> str:
    """Query token that does not appear in synthetic fixture content."""
    return "__no_match_query__"


def test_retrieve_calls_similarity_search_with_query_and_k() -> None:
    fake = FakeVectorStore(
        [
            Document(page_content="alpha", metadata={"source_doc_id": "a"}),
        ]
    )

    with patch.object(retrieve_mod, "load_vectorstore", return_value=fake):
        retrieve_mod.retrieve(
            "billing issue",
            initial_k=5,
            use_hybrid=False,
            use_rerank=False,
        )

    assert fake.calls == [{"query": "billing issue", "k": 5}]


def test_retrieve_limits_chunks_per_source() -> None:
    q = _docs_that_miss_query()
    docs = [
        Document(page_content=f"chunk a{i}", metadata={"source_doc_id": "policies/refund_policy_2026.md"})
        for i in range(4)
    ]
    docs += [
        Document(page_content=f"chunk b{i}", metadata={"source_doc_id": "hr/onboarding.md"})
        for i in range(3)
    ]
    fake = FakeVectorStore(docs)

    with patch.object(retrieve_mod, "load_vectorstore", return_value=fake):
        out = retrieve_mod.retrieve(
            q,
            initial_k=20,
            max_chunks_per_source=2,
            use_hybrid=False,
            use_rerank=False,
        )

    assert len(out) == 4
    by_source = {}
    for d in out:
        sid = d.metadata["source_doc_id"]
        by_source[sid] = by_source.get(sid, 0) + 1
    assert by_source["policies/refund_policy_2026.md"] == 2
    assert by_source["hr/onboarding.md"] == 2


def test_retrieve_handles_no_results() -> None:
    fake = FakeVectorStore([])

    with patch.object(retrieve_mod, "load_vectorstore", return_value=fake):
        out = retrieve_mod.retrieve(
            "anything",
            initial_k=8,
            use_hybrid=False,
            use_rerank=False,
        )

    assert out == []
    assert fake.calls == [{"query": "anything", "k": 8}]


def test_retrieve_preserves_metadata() -> None:
    meta = {
        "source_doc_id": "support/failed_payment_playbook.md",
        "domain": "support",
        "year": "2026",
        "topic": "failed_payment_playbook",
        "file_name": "failed_payment_playbook.md",
    }
    doc = Document(page_content="Escalate to payments on day three.", metadata=dict(meta))
    fake = FakeVectorStore([doc])

    with patch.object(retrieve_mod, "load_vectorstore", return_value=fake):
        out = retrieve_mod.retrieve(
            "Escalate",
            initial_k=4,
            use_hybrid=False,
            use_rerank=False,
        )

    assert len(out) == 1
    assert out[0].metadata == meta
    assert out[0].page_content == doc.page_content


def test_retrieve_filters_dense_results_for_single_year_query() -> None:
    docs = [
        Document(
            page_content="Refund window was 14 days.",
            metadata={"source_doc_id": "refund_2025", "file_name": "refund_policy_2025.md", "year": "2025"},
        ),
        Document(
            page_content="Refund window is 30 days.",
            metadata={"source_doc_id": "refund_2026", "file_name": "refund_policy_2026.md", "year": "2026"},
        ),
    ]
    fake = FakeVectorStore(docs)

    with patch.object(retrieve_mod, "load_vectorstore", return_value=fake):
        out = retrieve_mod.retrieve(
            "What was the refund window in 2025?",
            initial_k=4,
            use_hybrid=False,
            use_rerank=False,
        )

    assert [doc.metadata["file_name"] for doc in out] == ["refund_policy_2025.md"]
    assert fake.calls == [
        {
            "query": "What was the refund window in 2025?",
            "k": 4,
            "filter": {"year": "2025"},
            "fetch_k": 50,
        }
    ]


def test_retrieve_does_not_filter_dense_results_for_multi_year_query() -> None:
    fake = FakeVectorStore(
        [
            Document(page_content="2025 policy", metadata={"source_doc_id": "a", "year": "2025"}),
            Document(page_content="2026 policy", metadata={"source_doc_id": "b", "year": "2026"}),
        ]
    )

    with patch.object(retrieve_mod, "load_vectorstore", return_value=fake):
        retrieve_mod.retrieve(
            "Compare the 2025 and 2026 policies.",
            initial_k=4,
            use_hybrid=False,
            use_rerank=False,
        )

    assert fake.calls == [{"query": "Compare the 2025 and 2026 policies.", "k": 4}]


def test_retrieve_does_not_reintroduce_wrong_year_keyword_docs() -> None:
    dense_doc = Document(
        page_content="Refund window was 14 days.",
        metadata={"source_doc_id": "refund_2025", "file_name": "refund_policy_2025.md", "year": "2025"},
    )
    wrong_year_keyword_doc = Document(
        page_content="Refund window is 30 days.",
        metadata={"source_doc_id": "refund_2026", "file_name": "refund_policy_2026.md", "year": "2026"},
    )
    fake = FakeVectorStore([dense_doc, wrong_year_keyword_doc])

    with (
        patch.object(retrieve_mod, "load_vectorstore", return_value=fake),
        patch.object(retrieve_mod, "keyword_retrieve", return_value=[wrong_year_keyword_doc]),
    ):
        out = retrieve_mod.retrieve(
            "What was the refund window in 2025?",
            initial_k=4,
            use_hybrid=True,
            use_rerank=False,
        )

    assert [doc.metadata["file_name"] for doc in out] == ["refund_policy_2025.md"]


def test_main_passes_final_k_to_retrieve(capsys) -> None:
    with (
        patch.object(retrieve_mod, "retrieve", return_value=[]) as retrieve_mock,
        patch.object(sys, "argv", ["retrieve.py", "--query", "hello", "--k", "7"]),
    ):
        retrieve_mod.main()

    retrieve_mock.assert_called_once_with("hello", final_k=7)
    captured = capsys.readouterr()
    assert "Retrieved 0 documents." in captured.out
