from __future__ import annotations

import re
import warnings
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

    This model evaluates (query, document) pairs directly, giving much better
    relevance ranking than embedding similarity.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_rerank_model_name()
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=FutureWarning,
                message=".*resume_download.*",
            )
            self.model = CrossEncoder(self.model_name)

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
            (
                RerankedDocument(doc=doc, score=score)
                for doc, score in zip(docs, scores)
            ),
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


def parse_valid_year(value: object) -> int | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text.isdigit():
        return None

    return int(text)


def extract_query_year(query: str) -> int | None:
    match = re.search(r"\b(20\d{2})\b", query)
    if not match:
        return None
    return int(match.group(1))


def get_comparison_group_key(doc: Document) -> Tuple[str, str]:
    """
    Defines which documents should be compared for metadata adjustments.

    Grouping by (domain, topic) keeps year/recency comparisons local to similar
    document families (e.g. refund_policy versions).
    """
    domain = str(doc.metadata.get("domain", "")).strip().lower()
    topic = str(doc.metadata.get("topic", "")).strip().lower()
    return domain, topic


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


def compute_freshness_bonus(
    *,
    doc_year: int,
    min_year: int,
    max_year: int,
    max_bonus: float = 0.02,
) -> float:
    if min_year == max_year:
        return 0.0

    normalized = (doc_year - min_year) / (max_year - min_year)
    return normalized * max_bonus


def compute_group_metadata_adjustment(
    *,
    query: str,
    item: RerankedDocument,
    group_items: Sequence[RerankedDocument],
    max_freshness_bonus: float = 0.1,
    exact_year_match_bonus: float = 0.1,
    year_mismatch_penalty: float = 0.05,
) -> float:
    """
    Compute a small metadata-based score adjustment within a comparable group.

    Rules:
    - If the query contains an explicit year, prefer exact year matches and
      penalize mismatched years.
    - Otherwise, apply a small freshness bonus
    - If neither applies, return 0.0.
    """
    query_year = extract_query_year(query)
    doc_year = parse_valid_year(item.doc.metadata.get("year"))

    # Explicit year intent overrides generic freshness.
    if query_year is not None:
        if doc_year is None:
            return 0.0
        if doc_year == query_year:
            return exact_year_match_bonus
        return -year_mismatch_penalty

    # Otherwise, prefer the latest doc within the same (domain, topic) group.
    if doc_year is None:
        return 0.0

    year_range = get_valid_year_range(group_items)
    if year_range is None:
        return 0.0

    min_year, max_year = year_range
    return compute_freshness_bonus(
        doc_year=doc_year,
        min_year=min_year,
        max_year=max_year,
        max_bonus=max_freshness_bonus,
    )


def apply_metadata_score_adjustment(
    query: str,
    items: Sequence[RerankedDocument],
) -> List[RerankedDocument]:
    """
    Apply small metadata-based adjustments within comparable groups.

    - Cross-encoder score remains the primary signal.
    - Metadata adjustment is a soft secondary signal.
    - Comparisons remain local to the same (domain, topic) family.
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
            adjusted.extend(group_items)
            continue

        for item in group_items:
            adjustment = compute_group_metadata_adjustment(
                query=query,
                item=item,
                group_items=group_items,
            )
            adjusted.append(
                RerankedDocument(
                    doc=item.doc,
                    score=item.score + adjustment,
                )
            )

    adjusted.extend(ungrouped)
    return sorted(adjusted, key=lambda x: x.score, reverse=True)


def rerank_candidates(
    query: str,
    docs: Sequence[Document],
    reranker: CrossEncoderReranker | None = None,
    use_metadata_score_adjustment: bool = False,
) -> List[Document]:
    """
    Full reranking pipeline:
    1. Cross-encoder reranking (primary relevance)
    2. Optional metadata score adjustment (secondary signal)
    """
    if not docs:
        return []

    active_reranker = reranker or CrossEncoderReranker()
    ranked = active_reranker.rerank_with_scores(query, docs)

    if use_metadata_score_adjustment:
        ranked = apply_metadata_score_adjustment(query, ranked)

    return [item.doc for item in ranked]
