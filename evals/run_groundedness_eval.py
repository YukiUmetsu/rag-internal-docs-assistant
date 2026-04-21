from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml
from langchain_core.documents import Document


DEFAULT_GROUNDEDNESS_SCORE_THRESHOLD = 0.80
REASONABLE_SUPPORTED_MATCH_THRESHOLD = 0.75
REASONABLE_SEQUENCE_MATCH_THRESHOLD = 0.72
SCORABLE_CLAIM_LABELS = {"supported", "unsupported", "conflicting", "abstained"}

REFUSAL_PHRASES = (
    "cannot answer",
    "cannot provide",
    "can't answer",
    "can't provide",
    "cannot tell",
    "can't tell",
    "not enough context",
    "insufficient context",
    "not enough information",
    "could not find enough retrieved context",
    "no matching sources",
    "i don't know",
    "i cannot answer",
    "i cannot provide",
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "can",
    "do",
    "does",
    "for",
    "from",
    "has",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "should",
    "the",
    "their",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
}


def load_gold_queries(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data["queries"]


def normalize_eval_text(text: str) -> str:
    # Normalize whitespace and Unicode so small formatting differences do not
    # affect the groundedness checks.
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u202f", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_eval_text(text))


def significant_tokens(text: str) -> list[str]:
    # Drop common stopwords so overlap is driven by the words that carry meaning.
    return [token for token in tokenize(text) if token not in STOPWORDS]


def token_overlap_ratio(reference: str, candidate: str) -> float:
    # Measures how much of the claim's meaningful wording appears in the answer.
    # This gives a simple groundedness signal for paraphrases where exact string
    # matching would miss an otherwise supported claim.
    reference_tokens = significant_tokens(reference)
    if not reference_tokens:
        return 0.0

    candidate_tokens = set(significant_tokens(candidate))
    matches = sum(1 for token in reference_tokens if token in candidate_tokens)
    return matches / len(reference_tokens)


def answer_mentions_claim(answer: str, claim_text: str) -> bool:
    # Treat a claim as mentioned if the answer contains it exactly, overlaps on
    # the important words, or is close enough lexically to count as a paraphrase.
    answer_norm = normalize_eval_text(answer)
    claim_norm = normalize_eval_text(claim_text)
    if not claim_norm:
        return False
    if claim_norm in answer_norm:
        return True

    overlap_ratio = token_overlap_ratio(claim_text, answer)
    if overlap_ratio >= REASONABLE_SUPPORTED_MATCH_THRESHOLD:
        return True

    sequence_ratio = SequenceMatcher(None, claim_norm, answer_norm).ratio()
    return sequence_ratio >= REASONABLE_SEQUENCE_MATCH_THRESHOLD


def answer_contains_refusal(answer: str) -> bool:
    # Detect the common refusal phrases used when the answer abstains.
    answer_norm = normalize_eval_text(answer)
    return any(phrase in answer_norm for phrase in REFUSAL_PHRASES)


def extract_number_tokens(text: str) -> set[str]:
    return set(re.findall(r"\b\d+\b", normalize_eval_text(text)))


def get_document_source_names(doc: Document) -> set[str]:
    # Collect the common source identifiers so the scorer can match claims
    # against whichever metadata field the retriever surfaced.
    names: set[str] = set()
    for key in ("file_name", "source_doc_id", "canonical_doc_id"):
        value = doc.metadata.get(key)
        if not value:
            continue
        text = str(value).strip().lower()
        if not text:
            continue
        names.add(text)
        names.add(text.split("/")[-1])
    return names


def get_retrieved_source_names(docs: list[Document]) -> set[str]:
    names: set[str] = set()
    for doc in docs:
        names.update(get_document_source_names(doc))
    return names


def get_retrieved_file_names(docs: list[Document]) -> list[str]:
    file_names = {
        str(doc.metadata.get("file_name", "unknown")).strip()
        for doc in docs
        if str(doc.metadata.get("file_name", "unknown")).strip()
    }
    return sorted(file_names)


def claim_support_sources_satisfied(
    supported_by: set[str],
    retrieved_source_names: set[str],
    support_mode: str,
) -> bool:
    # Support mode controls whether a claim can be grounded by any one source
    # or whether it needs the full source set to be present.
    if not supported_by:
        return False
    if support_mode == "all":
        return supported_by.issubset(retrieved_source_names)
    return bool(retrieved_source_names & supported_by)


def format_groundedness_context(docs: list[Document]) -> str:
    # Keep the judge context compact but source-attributed so multi-source
    # support can be evaluated from the retrieved evidence.
    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("file_name", "unknown")
        parts.append(f"[Source {i}] {source}\n{doc.page_content}")
    return "\n\n".join(parts)


def extract_json_object(text: str) -> str:
    # Judges sometimes wrap JSON in markdown fences. This extracts the first
    # object so the evaluator can parse the verdict without brittle formatting
    # assumptions.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Judge response did not contain a JSON object")
    return text[start : end + 1]


def parse_judge_verdict(text: str) -> dict[str, Any]:
    payload = json.loads(extract_json_object(text))
    label = str(payload.get("label", "")).strip().lower()
    reason = str(payload.get("reason", "")).strip()
    if label not in {"supported", "unsupported", "conflicting", "abstained", "skipped"}:
        raise ValueError(f"Unexpected judge label: {label!r}")
    return {
        "label": label,
        "reason": reason or "judge returned no reason",
        "confidence": payload.get("confidence"),
    }


def judge_claim(
    *,
    answer: str,
    claim: dict[str, Any],
    retrieved_docs: list[Document],
    expected_behavior: str,
    llm: Any,
) -> dict[str, Any]:
    claim_text = str(claim.get("text", ""))
    supported_by = [
        str(source).strip()
        for source in claim.get("supported_by", [])
        if str(source).strip()
    ]
    conflict_with = [
        str(source).strip()
        for source in claim.get("conflict_with", [])
        if str(source).strip()
    ]
    prompt = (
        "You are grading groundedness for a RAG system.\n"
        "Return strict JSON only with keys: label, reason, confidence.\n"
        "label must be one of supported, unsupported, conflicting, abstained, skipped.\n"
        "Use skipped only if the claim is optional and the answer does not make that claim.\n"
        "Use supported when the answer states the claim and the retrieved context supports it.\n"
        "Use unsupported when the answer states the claim but the context does not support it.\n"
        "Use conflicting when the answer states a fact that contradicts the context.\n"
        "Use abstained when the answer correctly refuses because context is insufficient.\n"
        "Use multiple retrieved sources together when support is distributed across them.\n"
        "Do not mention chain-of-thought.\n\n"
        f"Claim ID: {claim.get('id')}\n"
        f"Claim text: {claim_text}\n"
        f"Critical: {bool(claim.get('critical', False))}\n"
        f"Optional: {bool(claim.get('optional', False))}\n"
        f"Expected behavior: {expected_behavior}\n"
        f"Supported by: {supported_by}\n"
        f"Conflict with: {conflict_with}\n\n"
        f"Answer:\n{answer}\n\n"
        f"Retrieved context:\n{format_groundedness_context(retrieved_docs)}\n"
    )

    response = llm.invoke(
        prompt,
        config={
            "run_name": "groundedness_judge",
            "tags": ["rag", "evaluation", "judge"],
            "metadata": {
                "claim_id": claim.get("id"),
                "critical": bool(claim.get("critical", False)),
                "optional": bool(claim.get("optional", False)),
                "doc_count": len(retrieved_docs),
            },
        },
    )
    return parse_judge_verdict(getattr(response, "content", str(response)))


def score_claim(
    *,
    answer: str,
    claim: dict[str, Any],
    retrieved_source_names: set[str],
    retrieved_docs: list[Document],
    expected_behavior: str,
    judge_mode: str,
    judge_llm: Any | None,
) -> dict[str, Any]:
    claim_text = str(claim.get("text", ""))
    supported_by = {
        str(source).strip().lower()
        for source in claim.get("supported_by", [])
        if str(source).strip()
    }
    conflict_with = {
        str(source).strip().lower()
        for source in claim.get("conflict_with", [])
        if str(source).strip()
    }
    critical = bool(claim.get("critical", False))
    claim_type = str(claim.get("type", "factual"))
    must_appear_in_answer = bool(claim.get("must_appear_in_answer", True))
    optional = bool(claim.get("optional", False))
    support_mode = str(claim.get("support_mode", "any")).lower()
    answer_mentions = answer_mentions_claim(answer, claim_text) if must_appear_in_answer else False

    if optional and judge_mode == "heuristic" and not answer_mentions:
        return {
            "id": claim.get("id"),
            "text": claim_text,
            "type": claim_type,
            "critical": critical,
            "supported_by": sorted(supported_by),
            "support_mode": support_mode,
            "conflict_with": sorted(conflict_with),
            "must_appear_in_answer": must_appear_in_answer,
            "optional": optional,
            "judge_mode": judge_mode,
            "judge_used": False,
            "triggered": False,
            "answer_mentions": False,
            "support_sources_present": False,
            "support_sources_matched": [],
            "conflict_sources_present": False,
            "label": "skipped",
            "reason": "optional claim not activated by the answer",
        }

    judge_result: dict[str, Any] | None = None
    if judge_mode in {"judge", "hybrid"} and judge_llm is not None:
        try:
            judge_result = judge_claim(
                answer=answer,
                claim=claim,
                retrieved_docs=retrieved_docs,
                expected_behavior=expected_behavior,
                llm=judge_llm,
            )
        except Exception:
            if judge_mode == "judge":
                raise

    support_sources_matched = retrieved_source_names & supported_by if supported_by else set()

    # Source support and answer wording are checked separately:
    # retrieval can be correct even when the answer never states the claim.
    support_sources_present = claim_support_sources_satisfied(supported_by, retrieved_source_names, support_mode)
    conflict_sources_present = bool(retrieved_source_names & conflict_with) if conflict_with else False
    refusal = answer_contains_refusal(answer)

    label = "unsupported"
    reason = "claim not grounded in the retrieved context"
    judge_used = judge_result is not None

    if judge_result is not None:
        label = str(judge_result["label"])
        reason = str(judge_result["reason"])
    elif expected_behavior == "abstain" and refusal:
        label = "abstained"
        reason = "answer correctly refused due to insufficient context"
    else:
        if support_sources_present and answer_mentions:
            label = "supported"
            reason = "claim is stated in the answer and supported by retrieved sources"
        elif conflict_sources_present and not answer_mentions:
            claim_numbers = extract_number_tokens(claim_text)
            answer_numbers = extract_number_tokens(answer)
            if claim_numbers and answer_numbers and any(number not in claim_numbers for number in answer_numbers):
                label = "conflicting"
                reason = "answer uses a different numeric fact while conflicting sources are present"
            elif not claim_numbers and not answer_mentions:
                label = "conflicting"
                reason = "answer conflicts with a retrieved source family"
        elif support_mode == "all" and support_sources_matched and not support_sources_present:
            label = "unsupported"
            missing_sources = sorted(supported_by - support_sources_matched)
            reason = (
                "answer is using a multi-source claim, but not all supporting sources "
                f"were retrieved; missing={missing_sources}"
            )
        elif answer_mentions and not support_sources_present:
            label = "unsupported"
            reason = "answer states the claim without retrieving a supporting source"
        elif not answer_mentions and support_sources_present:
            label = "unsupported"
            reason = "supporting source was retrieved but the claim is not stated clearly in the answer"

        if expected_behavior != "abstain" and conflict_sources_present and label == "unsupported":
            claim_numbers = extract_number_tokens(claim_text)
            answer_numbers = extract_number_tokens(answer)
            if claim_numbers and answer_numbers and any(number not in claim_numbers for number in answer_numbers):
                label = "conflicting"
                reason = "answer includes a different numeric fact than the claim"

    return {
        "id": claim.get("id"),
        "text": claim_text,
        "type": claim_type,
        "critical": critical,
        "supported_by": sorted(supported_by),
        "support_mode": support_mode,
        "conflict_with": sorted(conflict_with),
        "must_appear_in_answer": must_appear_in_answer,
        "optional": optional,
        "judge_mode": judge_mode,
        "judge_used": judge_used,
        "triggered": True,
        "answer_mentions": answer_mentions,
        "support_sources_present": support_sources_present,
        "support_sources_matched": sorted(support_sources_matched),
        "conflict_sources_present": conflict_sources_present,
        "label": label,
        "reason": reason,
    }


def score_row(
    item: dict[str, Any],
    *,
    answer_mode: str,
    judge_mode: str,
    vectorstore_path: str,
    chunks_path: str,
    retriever_backend: str | None,
    final_k: int,
    initial_k: int,
    max_chunks_per_source: int,
    debug_log_path: str | None,
    judge_llm: Any | None,
) -> dict[str, Any]:
    query_id = item["id"]
    category = item.get("category", "uncategorized")
    query = item["query"]
    expected_sources = item.get("expected_sources", [])
    expected_behavior = item.get("expected_behavior", "answer")
    claims = item.get("claims", [])

    # Import the retrieval stack here so the scoring helpers stay testable even
    # when optional retriever dependencies are not installed.
    from src.rag.retrieve import retrieve

    retrieval_start = time.perf_counter()
    docs = retrieve(
        query=query,
        final_k=final_k,
        initial_k=initial_k,
        max_chunks_per_source=max_chunks_per_source,
        vectorstore_path=vectorstore_path,
        chunks_path=chunks_path,
        retriever_backend=retriever_backend,
        use_hybrid=True,
        use_rerank=True,
        debug_log_path=debug_log_path,
        debug_context={
            "query_id": query_id,
            "mode_name": "groundedness",
        },
    )
    retrieval_latency_ms = int((time.perf_counter() - retrieval_start) * 1000)

    generation_start = time.perf_counter()
    answer_mode_used = answer_mode
    warning = None
    if answer_mode == "mock":
        from src.backend.app.services.rag_service import build_mock_answer

        answer = build_mock_answer(docs)
    else:
        try:
            from src.rag.answer import generate_answer_from_docs

            answer = generate_answer_from_docs(question=query, docs=docs)
            answer_mode_used = "live"
        except Exception as exc:  # pragma: no cover - defensive fallback
            from src.backend.app.services.rag_service import build_mock_answer

            answer = build_mock_answer(docs)
            answer_mode_used = "mock_fallback"
            warning = f"Live answer generation failed; using mock fallback. {type(exc).__name__}: {exc}"
    generation_latency_ms = int((time.perf_counter() - generation_start) * 1000)

    retrieved_source_names = get_retrieved_source_names(docs)
    # Each claim is scored independently so one bad statement does not hide
    # support for the rest of the answer.
    claim_results = [
        score_claim(
            answer=answer,
            claim=claim,
            retrieved_source_names=retrieved_source_names,
            retrieved_docs=docs,
            expected_behavior=expected_behavior,
            judge_mode=judge_mode,
            judge_llm=judge_llm,
        )
        for claim in claims
    ]

    supported_claim_count = sum(1 for result in claim_results if result["label"] == "supported")
    unsupported_claim_count = sum(1 for result in claim_results if result["label"] == "unsupported")
    conflicting_claim_count = sum(1 for result in claim_results if result["label"] == "conflicting")
    abstained_claim_count = sum(1 for result in claim_results if result["label"] == "abstained")
    skipped_claim_count = sum(1 for result in claim_results if result["label"] == "skipped")
    critical_claim_count = sum(1 for result in claim_results if result["critical"] and result["label"] in SCORABLE_CLAIM_LABELS)
    critical_unsupported_count = sum(
        1
        for result in claim_results
        if result["critical"] and result["label"] in {"unsupported", "conflicting"}
    )

    refusal = answer_contains_refusal(answer)
    appropriate_abstain = expected_behavior == "abstain" and refusal and critical_unsupported_count == 0 and conflicting_claim_count == 0
    overconfident = expected_behavior == "abstain" and not refusal
    row_pass = (
        (expected_behavior == "abstain" and refusal and critical_unsupported_count == 0 and conflicting_claim_count == 0)
        or (
            expected_behavior != "abstain"
            and critical_unsupported_count == 0
            and conflicting_claim_count == 0
        )
    )

    total_claims = supported_claim_count + unsupported_claim_count + conflicting_claim_count + abstained_claim_count
    # These aggregate metrics separate support, contradiction, and abstention
    # so the final score reflects different failure modes.
    supported_claim_rate = supported_claim_count / total_claims if total_claims else 0.0
    unsupported_claim_rate = unsupported_claim_count / total_claims if total_claims else 0.0
    conflict_rate = conflicting_claim_count / total_claims if total_claims else 0.0
    abstain_rate = abstained_claim_count / total_claims if total_claims else 0.0
    groundedness_score = supported_claim_rate - conflict_rate - 0.5 * unsupported_claim_rate

    return {
        "id": query_id,
        "category": category,
        "query": query,
        "expected_sources": expected_sources,
        "retrieved_sources": get_retrieved_file_names(docs),
        "expected_behavior": expected_behavior,
        "judge_mode": judge_mode,
        "answer": answer,
        "answer_mode_requested": answer_mode,
        "answer_mode_used": answer_mode_used,
        "warning": warning,
        "retrieval_latency_ms": retrieval_latency_ms,
        "generation_latency_ms": generation_latency_ms,
        "latency_ms": retrieval_latency_ms + generation_latency_ms,
        "claim_results": claim_results,
        "total_claims": total_claims,
        "skipped_claim_count": skipped_claim_count,
        "supported_claim_count": supported_claim_count,
        "unsupported_claim_count": unsupported_claim_count,
        "conflicting_claim_count": conflicting_claim_count,
        "abstained_claim_count": abstained_claim_count,
        "critical_claim_count": critical_claim_count,
        "critical_unsupported_count": critical_unsupported_count,
        "row_pass": row_pass,
        "appropriate_abstain": appropriate_abstain,
        "overconfident": overconfident,
        "supported_claim_rate": supported_claim_rate,
        "unsupported_claim_rate": unsupported_claim_rate,
        "conflict_rate": conflict_rate,
        "abstain_rate": abstain_rate,
        "groundedness_score": groundedness_score,
    }


def evaluate_groundedness(
    gold_queries: list[dict[str, Any]],
    *,
    answer_mode: str,
    judge_mode: str,
    vectorstore_path: str,
    chunks_path: str,
    retriever_backend: str | None,
    final_k: int = 4,
    initial_k: int = 12,
    max_chunks_per_source: int = 2,
    debug_log_path: str | None = None,
    judge_llm: Any | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    category_totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "count": 0,
            "supported_claims": 0,
            "unsupported_claims": 0,
            "conflicting_claims": 0,
            "abstained_claims": 0,
            "skipped_claims": 0,
            "critical_claims": 0,
            "critical_unsupported_claims": 0,
            "passed_rows": 0,
            "should_abstain_rows": 0,
            "correct_abstains": 0,
            "overconfident_rows": 0,
            "groundedness_score": 0.0,
        }
    )

    total_supported_claims = 0
    total_unsupported_claims = 0
    total_conflicting_claims = 0
    total_abstained_claims = 0
    total_critical_claims = 0
    total_critical_unsupported_claims = 0
    total_rows_passed = 0
    total_should_abstain_rows = 0
    total_correct_abstains = 0
    total_overconfident_rows = 0
    total_groundedness_score = 0.0

    for item in gold_queries:
        row_result = score_row(
            item,
            answer_mode=answer_mode,
            judge_mode=judge_mode,
            vectorstore_path=vectorstore_path,
            chunks_path=chunks_path,
            retriever_backend=retriever_backend,
            final_k=final_k,
            initial_k=initial_k,
            max_chunks_per_source=max_chunks_per_source,
            debug_log_path=debug_log_path,
            judge_llm=judge_llm,
        )
        rows.append(row_result)

        category = row_result["category"]
        totals = category_totals[category]
        totals["count"] += 1
        totals["supported_claims"] += row_result["supported_claim_count"]
        totals["unsupported_claims"] += row_result["unsupported_claim_count"]
        totals["conflicting_claims"] += row_result["conflicting_claim_count"]
        totals["abstained_claims"] += row_result["abstained_claim_count"]
        totals["skipped_claims"] += row_result["skipped_claim_count"]
        totals["critical_claims"] += row_result["critical_claim_count"]
        totals["critical_unsupported_claims"] += row_result["critical_unsupported_count"]
        totals["passed_rows"] += 1 if row_result["row_pass"] else 0
        totals["groundedness_score"] += row_result["groundedness_score"]

        if row_result["expected_behavior"] == "abstain":
            totals["should_abstain_rows"] += 1
            total_should_abstain_rows += 1
            if row_result["appropriate_abstain"]:
                totals["correct_abstains"] += 1
                total_correct_abstains += 1
            if row_result["overconfident"]:
                totals["overconfident_rows"] += 1
                total_overconfident_rows += 1

        total_supported_claims += row_result["supported_claim_count"]
        total_unsupported_claims += row_result["unsupported_claim_count"]
        total_conflicting_claims += row_result["conflicting_claim_count"]
        total_abstained_claims += row_result["abstained_claim_count"]
        total_critical_claims += row_result["critical_claim_count"]
        total_critical_unsupported_claims += row_result["critical_unsupported_count"]
        total_rows_passed += 1 if row_result["row_pass"] else 0
        total_groundedness_score += row_result["groundedness_score"]

    num_rows = len(gold_queries)
    num_claims = total_supported_claims + total_unsupported_claims + total_conflicting_claims + total_abstained_claims
    num_skipped_claims = sum(row["skipped_claim_count"] for row in rows)

    # The summary keeps row-level failures visible while also reporting claim-
    # level rates for overall groundedness.
    summary = {
        "num_rows": num_rows,
        "num_claims": num_claims,
        "num_skipped_claims": num_skipped_claims,
        "supported_claim_rate": total_supported_claims / num_claims if num_claims else 0.0,
        "unsupported_claim_rate": total_unsupported_claims / num_claims if num_claims else 0.0,
        "conflict_rate": total_conflicting_claims / num_claims if num_claims else 0.0,
        "abstain_rate": total_abstained_claims / num_claims if num_claims else 0.0,
        "critical_claim_count": total_critical_claims,
        "critical_unsupported_rate": total_critical_unsupported_claims / total_critical_claims if total_critical_claims else 0.0,
        "row_pass_rate": total_rows_passed / num_rows if num_rows else 0.0,
        "appropriate_abstain_rate": total_correct_abstains / total_should_abstain_rows if total_should_abstain_rows else None,
        "overconfident_answer_rate": total_overconfident_rows / total_should_abstain_rows if total_should_abstain_rows else None,
        "groundedness_score": total_groundedness_score / num_rows if num_rows else 0.0,
        "answer_mode": answer_mode,
        "judge_mode": judge_mode,
    }

    category_summary: dict[str, dict[str, float]] = {}
    for category, totals in category_totals.items():
        count = totals["count"]
        total_claims_for_category = (
            totals["supported_claims"]
            + totals["unsupported_claims"]
            + totals["conflicting_claims"]
            + totals["abstained_claims"]
        )
        category_summary[category] = {
            "count": count,
            "skipped_claims": totals["skipped_claims"],
            "supported_claim_rate": totals["supported_claims"] / total_claims_for_category if total_claims_for_category else 0.0,
            "unsupported_claim_rate": totals["unsupported_claims"] / total_claims_for_category if total_claims_for_category else 0.0,
            "conflict_rate": totals["conflicting_claims"] / total_claims_for_category if total_claims_for_category else 0.0,
            "abstain_rate": totals["abstained_claims"] / total_claims_for_category if total_claims_for_category else 0.0,
            "critical_unsupported_rate": totals["critical_unsupported_claims"] / totals["critical_claims"] if totals["critical_claims"] else 0.0,
            "row_pass_rate": totals["passed_rows"] / count if count else 0.0,
            "appropriate_abstain_rate": totals["correct_abstains"] / totals["should_abstain_rows"] if totals["should_abstain_rows"] else None,
            "overconfident_answer_rate": totals["overconfident_rows"] / totals["should_abstain_rows"] if totals["should_abstain_rows"] else None,
            "groundedness_score": totals["groundedness_score"] / count if count else 0.0,
        }

    return {
        "summary": summary,
        "category_summary": category_summary,
        "rows": rows,
    }


def format_optional_rate(value: float | None) -> str:
    if value is None:
        return "skipped"
    return f"{value:.3f}"


def print_summary(result: dict[str, Any]) -> None:
    # Print the same core metrics that appear in the JSON artifact.
    summary = result["summary"]
    category_summary = result["category_summary"]

    print("\n=== groundedness ===")
    print(f"rows                   : {summary['num_rows']}")
    print(f"claims                 : {summary['num_claims']}")
    print(f"skipped_claims         : {summary['num_skipped_claims']}")
    print(f"row_pass_rate          : {summary['row_pass_rate']:.3f}")
    print(f"supported_claim_rate   : {summary['supported_claim_rate']:.3f}")
    print(f"unsupported_claim_rate : {summary['unsupported_claim_rate']:.3f}")
    print(f"conflict_rate          : {summary['conflict_rate']:.3f}")
    print(f"abstain_rate           : {summary['abstain_rate']:.3f}")
    print(f"critical_unsupported   : {summary['critical_unsupported_rate']:.3f}")
    print(f"groundedness_score     : {summary['groundedness_score']:.3f}")
    print(f"appropriate_abstain    : {format_optional_rate(summary['appropriate_abstain_rate'])}")
    print(f"overconfident_answer   : {format_optional_rate(summary['overconfident_answer_rate'])}")
    print(f"answer_mode            : {summary['answer_mode']}")
    print(f"judge_mode             : {summary['judge_mode']}")

    if category_summary:
        print("by_category:")
        for category, metrics in category_summary.items():
            print(
                f"  - {category}: "
                f"count={metrics['count']}, "
                f"skipped_claims={metrics['skipped_claims']}, "
                f"row_pass_rate={metrics['row_pass_rate']:.3f}, "
                f"groundedness_score={metrics['groundedness_score']:.3f}, "
                f"critical_unsupported_rate={metrics['critical_unsupported_rate']:.3f}"
            )


def require_minimum_metrics(
    result: dict[str, Any],
    *,
    groundedness_score: float | None,
    critical_unsupported_rate: float | None,
    conflict_rate: float | None,
    appropriate_abstain_rate: float | None,
) -> None:
    summary = result["summary"]
    failures: list[str] = []

    # Groundedness is better when the score is high and the unsupported and
    # conflicting rates stay low.
    if groundedness_score is not None and summary["groundedness_score"] < groundedness_score:
        failures.append(
            f"groundedness_score expected >= {groundedness_score:.3f}, got {summary['groundedness_score']:.3f}"
        )

    if critical_unsupported_rate is not None and summary["critical_unsupported_rate"] > critical_unsupported_rate:
        failures.append(
            f"critical_unsupported_rate expected <= {critical_unsupported_rate:.3f}, got {summary['critical_unsupported_rate']:.3f}"
        )

    if conflict_rate is not None and summary["conflict_rate"] > conflict_rate:
        failures.append(
            f"conflict_rate expected <= {conflict_rate:.3f}, got {summary['conflict_rate']:.3f}"
        )

    if appropriate_abstain_rate is not None:
        current_value = summary["appropriate_abstain_rate"]
        if current_value is None or current_value < appropriate_abstain_rate:
            failures.append(
                f"appropriate_abstain_rate expected >= {appropriate_abstain_rate:.3f}, got {current_value if current_value is not None else 'skipped'}"
            )

    if failures:
        print("\nMetric requirements failed:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run groundedness evaluation.")
    parser.add_argument("--gold-path", default="evals/groundedness_gold.yaml")
    parser.add_argument("--vectorstore-path", default="artifacts/faiss_index")
    parser.add_argument("--chunks-path", default="artifacts/chunks.jsonl")
    parser.add_argument(
        "--retriever-backend",
        choices=["faiss", "postgres"],
        default=None,
        help="Override the retriever backend used for evaluation.",
    )
    parser.add_argument("--output-path", default="artifacts/evals/groundedness_eval_results.json")
    parser.add_argument("--final-k", type=int, default=4)
    parser.add_argument("--initial-k", type=int, default=12)
    parser.add_argument("--max-chunks-per-source", type=int, default=2)
    parser.add_argument("--debug-log-path", default="artifacts/evals/groundedness_debug.jsonl")
    parser.add_argument(
        "--answer-mode",
        choices=["live", "mock"],
        default="live",
        help="Choose live generation or the mock answer path.",
    )
    parser.add_argument("--require-groundedness-score", type=float, default=DEFAULT_GROUNDEDNESS_SCORE_THRESHOLD)
    parser.add_argument("--require-critical-unsupported-rate", type=float, default=0.0)
    parser.add_argument("--require-conflict-rate", type=float, default=0.0)
    parser.add_argument("--require-appropriate-abstain-rate", type=float)
    parser.add_argument(
        "--judge-mode",
        choices=["heuristic", "judge", "hybrid"],
        default="heuristic",
        help="Choose heuristic scoring, LLM judging, or a hybrid fallback mode.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold_queries = load_gold_queries(args.gold_path)

    judge_llm: Any | None = None
    if args.judge_mode in {"judge", "hybrid"}:
        from src.rag.llm import get_judge_llm

        judge_llm = get_judge_llm()

    result = evaluate_groundedness(
        gold_queries,
        answer_mode=args.answer_mode,
        judge_mode=args.judge_mode,
        vectorstore_path=args.vectorstore_path,
        chunks_path=args.chunks_path,
        retriever_backend=args.retriever_backend,
        final_k=args.final_k,
        initial_k=args.initial_k,
        max_chunks_per_source=args.max_chunks_per_source,
        debug_log_path=args.debug_log_path,
        judge_llm=judge_llm,
    )

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"groundedness": result}, indent=2),
        encoding="utf-8",
    )

    print_summary(result)

    require_minimum_metrics(
        result,
        groundedness_score=args.require_groundedness_score,
        critical_unsupported_rate=args.require_critical_unsupported_rate,
        conflict_rate=args.require_conflict_rate,
        appropriate_abstain_rate=args.require_appropriate_abstain_rate,
    )

    print(f"\nWrote groundedness results to {output_path}")


if __name__ == "__main__":
    main()
