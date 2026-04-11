from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.documents import Document

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.rag import chunking as chunking_mod

_MD_CHUNK_SIZE = 700
_MD_CHUNK_OVERLAP = 120
_PDF_CHUNK_SIZE = 500


def _max_suffix_prefix_overlap(left: str, right: str, max_len: int = 256) -> int:
    """Longest suffix of `left` that matches a prefix of `right`."""
    best = 0
    upper = min(len(left), len(right), max_len)
    for k in range(1, upper + 1):
        if right.startswith(left[-k:]):
            best = k
    return best


def _markdown_doc(body: str) -> Document:
    return Document(
        page_content=body,
        metadata={"file_type": "md", "source": "policies/example.md"},
    )


def _pdf_doc(body: str, *, page: int = 1) -> Document:
    return Document(
        page_content=body,
        metadata={
            "file_type": "pdf",
            "source": "/data/hr/handbook.pdf",
            "page": page,
        },
    )


def test_markdown_chunking_keeps_expected_number_of_chunks() -> None:
    # Long, separator-light text forces several size-based splits (not a single heading block).
    long_body = ("word " * 600).strip()
    assert len(long_body) > _MD_CHUNK_SIZE
    doc = _markdown_doc(long_body)

    chunks = chunking_mod.split_documents([doc])
    reference = chunking_mod.get_markdown_splitter().split_documents([doc])

    assert chunks == reference
    assert len(chunks) > 1
    for ch in chunks:
        assert len(ch.page_content) <= _MD_CHUNK_SIZE


def test_markdown_chunking_preserves_overlap() -> None:
    # test that overlap is actually present between adjacent chunks
    long_body = ("token-" * 400).strip()
    doc = _markdown_doc(long_body)
    chunks = chunking_mod.split_documents([doc])

    assert len(chunks) >= 2
    for ch in chunks:
        assert len(ch.page_content) <= _MD_CHUNK_SIZE

    for prev, nxt in zip(chunks, chunks[1:]):
        shared = _max_suffix_prefix_overlap(prev.page_content, nxt.page_content)
        # Separator-aware splits can shorten the exact boundary match; still expect
        # a substantial shared prefix/suffix region when overlap is configured.
        assert shared >= min(80, _MD_CHUNK_OVERLAP)


def test_pdf_chunking_produces_chunks_with_page_metadata() -> None:
    body = ("paragraph " * 80).strip()
    assert len(body) > _PDF_CHUNK_SIZE
    doc = _pdf_doc(body, page=4)

    chunks = chunking_mod.split_documents([doc])
    reference = chunking_mod.get_pdf_splitter().split_documents([doc])

    assert chunks == reference
    assert len(chunks) > 1
    for ch in chunks:
        assert ch.metadata.get("page") == 4
        assert ch.metadata.get("source") == "/data/hr/handbook.pdf"
        assert len(ch.page_content) <= _PDF_CHUNK_SIZE


def test_empty_and_tiny_documents_do_not_crash_chunking() -> None:
    for content in ("", "x", "hi"):
        md_chunks = chunking_mod.split_documents([_markdown_doc(content)])
        pdf_chunks = chunking_mod.split_documents([_pdf_doc(content, page=1)])
        assert isinstance(md_chunks, list)
        assert isinstance(pdf_chunks, list)
