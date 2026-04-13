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
        retrieve_mod.retrieve("billing issue", initial_k=5)

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
        out = retrieve_mod.retrieve(q, initial_k=20, max_chunks_per_source=2)

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
        out = retrieve_mod.retrieve("anything", initial_k=8)

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
        out = retrieve_mod.retrieve("Escalate", initial_k=4)

    assert len(out) == 1
    assert out[0].metadata == meta
    assert out[0].page_content == doc.page_content
