from langchain_core.documents import Document
from src.rag.rerank import (
    RerankedDocument,
    apply_freshness_bonus,
    get_valid_year_range,
    parse_valid_year,
)

def make_reranked_doc(
    content: str,
    score: float,
    *,
    domain: str = "",
    topic: str = "",
    year: str | int | None = None,
    file_name: str = "doc.md",
) -> RerankedDocument:
    return RerankedDocument(
        doc=Document(
            page_content=content,
            metadata={
                "domain": domain,
                "topic": topic,
                "year": year,
                "file_name": file_name,
            },
        ),
        score=score,
    )

def test_parse_valid_year():
    assert parse_valid_year("2026") == 2026
    assert parse_valid_year(2025) == 2025
    assert parse_valid_year("abc") is None
    assert parse_valid_year(None) is None


def test_get_valid_year_range_ignores_invalid_years():
    items = [
        make_reranked_doc("a", 0.8, year="2024"),
        make_reranked_doc("b", 0.7, year="bad"),
        make_reranked_doc("c", 0.6, year="2026"),
    ]

    assert get_valid_year_range(items) == (2024, 2026)


def test_apply_freshness_bonus_prefers_newer_doc_within_same_group():
    items = [
        make_reranked_doc(
            "older refund policy",
            0.90,
            domain="policies",
            topic="refund_policy",
            year="2025",
            file_name="refund_policy_2025.md",
        ),
        make_reranked_doc(
            "newer refund policy",
            0.89,
            domain="policies",
            topic="refund_policy",
            year="2026",
            file_name="refund_policy_2026.md",
        ),
    ]

    ranked = apply_freshness_bonus(items, max_bonus=0.02)

    assert ranked[0].doc.metadata["file_name"] == "refund_policy_2026.md"


def test_apply_freshness_bonus_does_not_mix_topics():
    items = [
        make_reranked_doc(
            "refund doc",
            0.71,
            domain="policies",
            topic="refund_policy",
            year="2025",
            file_name="refund_policy_2025.md",
        ),
        make_reranked_doc(
            "hr handbook",
            0.70,
            domain="hr",
            topic="employee_handbook",
            year="2026",
            file_name="employee_handbook_2026.md",
        ),
    ]

    ranked = apply_freshness_bonus(items, max_bonus=0.02)

    assert ranked[0].doc.metadata["file_name"] == "refund_policy_2025.md"


def test_apply_freshness_bonus_skips_single_item_group():
    items = [
        make_reranked_doc(
            "single doc",
            0.80,
            domain="hr",
            topic="pto_policy",
            year="2026",
            file_name="pto_policy_2026.md",
        )
    ]

    ranked = apply_freshness_bonus(items, max_bonus=0.02)

    assert ranked[0].score == 0.80
    assert ranked[0].doc.metadata["file_name"] == "pto_policy_2026.md"


def test_apply_freshness_bonus_skips_same_year_group():
    items = [
        make_reranked_doc(
            "doc 1",
            0.91,
            domain="hr",
            topic="pto_policy",
            year="2026",
            file_name="pto_policy_a.md",
        ),
        make_reranked_doc(
            "doc 2",
            0.89,
            domain="hr",
            topic="pto_policy",
            year="2026",
            file_name="pto_policy_b.md",
        ),
    ]

    ranked = apply_freshness_bonus(items, max_bonus=0.02)

    assert [item.doc.metadata["file_name"] for item in ranked] == [
        "pto_policy_a.md",
        "pto_policy_b.md",
    ]