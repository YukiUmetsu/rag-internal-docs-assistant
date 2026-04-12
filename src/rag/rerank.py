from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from src.rag.config import get_rerank_model_name


# ----------------------------
# Data structure
# ----------------------------

@dataclass(frozen=True)
class RerankedDocument:
    doc: Document
    score: float


# ----------------------------
# Cross-encoder reranker
# ----------------------------

class CrossEncoderReranker:
    """
    Second-stage reranker using a cross-encoder.

    This model evaluates (query, document) pairs directly,
    giving much better relevance ranking than embedding similarity.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_rerank_model_name()
        self.model = CrossEncoder(model_name)

    def score(self, query: str, docs: Sequence[Document]) -> List[float]:
        if not docs:
            return []

        pairs = [(query, doc.page_content) for doc in docs]
        scores = self.model.predict(pairs)

        return [float(s) for s in scores]

    def rerank_with_scores(
        self,
        query: str,
        docs: Sequence[Document],
    ) -> List[RerankedDocument]:
        if not docs:
            return []

        scores = self.score(query, docs)

        ranked = sorted(
            (RerankedDocument(doc=doc, score=score) for doc, score in zip(docs, scores)),
            key=lambda x: x.score,
            reverse=True,
        )

        return ranked

    def rerank(
        self,
        query: str,
        docs: Sequence[Document],
    ) -> List[Document]:
        ranked = self.rerank_with_scores(query, docs)
        return [item.doc for item in ranked]


# ----------------------------
# Freshness helpers
# ----------------------------

def parse_valid_year(value: object) -> int | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text.isdigit():
        return None

    return int(text)


def get_valid_year_range(
    items: Sequence[RerankedDocument],
) -> Tuple[int, int] | None:
    years = [
        year
        for item in items
        if (year := parse_valid_year(item.doc.metadata.get("year"))) is not None
    ]

    if not years:
        return None

    return min(years), max(years)


def get_comparison_group_key(doc: Document) -> Tuple[str, str]:
    """
    Defines which documents should be compared for freshness.

    Grouping by (domain, topic) keeps recency comparisons local
    to similar document families (e.g. refund_policy versions).
    """
    domain = str(doc.metadata.get("domain", "")).strip().lower()
    topic = str(doc.metadata.get("topic", "")).strip().lower()
    return domain, topic


# ----------------------------
# Freshness-aware reranking
# ----------------------------

def apply_freshness_bonus(
    items: Sequence[RerankedDocument],
    max_bonus: float = 0.02,
) -> List[RerankedDocument]:
    """
    Apply a small normalized recency bonus within comparable groups.

    - Cross-encoder score remains primary signal
    - Freshness is a soft adjustment (not a hard override)
    - Only applies within same (domain, topic)
    """

    grouped: dict[Tuple[str, str], List[RerankedDocument]] = defaultdict(list)
    ungrouped: List[RerankedDocument] = []

    for item in items:
        key = get_comparison_group_key(item.doc)

        if key == ("", ""):
            ungrouped.append(item)
        else:
            grouped[key].append(item)

    adjusted: List[RerankedDocument] = []

    for group_items in grouped.values():

        if len(group_items) < 2:
            # not enough items to compare within the group
            adjusted.extend(group_items)
            continue

        year_range = get_valid_year_range(group_items)

        if year_range is None:
            adjusted.extend(group_items)
            continue

        min_year, max_year = year_range

        if min_year == max_year:
            adjusted.extend(group_items)
            continue

        for item in group_items:
            year = parse_valid_year(item.doc.metadata.get("year"))
            bonus = 0.0

            if year is not None:
                normalized = (year - min_year) / (max_year - min_year)
                bonus = normalized * max_bonus

            adjusted.append(
                RerankedDocument(
                    doc=item.doc,
                    score=item.score + bonus,
                )
            )

    adjusted.extend(ungrouped)

    return sorted(adjusted, key=lambda x: x.score, reverse=True)


# ----------------------------
# Public helper for retrieve.py
# ----------------------------

def rerank_candidates(
    query: str,
    docs: Sequence[Document],
    reranker: CrossEncoderReranker | None = None,
    apply_freshness: bool = True,
) -> List[Document]:
    """
    Full reranking pipeline:

    1. Cross-encoder reranking (primary relevance)
    2. Optional freshness bonus (secondary signal)
    """

    if not docs:
        return []

    active_reranker = reranker or CrossEncoderReranker()

    ranked = active_reranker.rerank_with_scores(query, docs)

    if apply_freshness:
        ranked = apply_freshness_bonus(ranked)

    return [item.doc for item in ranked]