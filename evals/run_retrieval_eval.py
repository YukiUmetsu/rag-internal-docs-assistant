from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from src.rag.retrieve import retrieve
from src.rag.answer import generate_answer_from_docs


def load_gold_queries(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["queries"]


def hit_at_k(retrieved_sources: list[str], expected_sources: list[str]) -> int:
    expected = set(expected_sources)
    return int(any(source in expected for source in retrieved_sources))


def reciprocal_rank(retrieved_sources: list[str], expected_sources: list[str]) -> float:
    expected = set(expected_sources)
    for idx, source in enumerate(retrieved_sources, start=1):
        if source in expected:
            return 1.0 / idx
    return 0.0


def top_1_correct(retrieved_sources: list[str], expected_sources: list[str]) -> int:
    if not retrieved_sources:
        return 0
    return int(retrieved_sources[0] in set(expected_sources))


def fact_hit(answer: str, expected_facts: list[str]) -> int:
    if not expected_facts:
        return 1
    answer_lower = answer.lower()
    return int(any(fact.lower() in answer_lower for fact in expected_facts))


def all_facts_hit(answer: str, expected_facts: list[str]) -> int:
    if not expected_facts:
        return 1
    answer_lower = answer.lower()
    return int(all(fact.lower() in answer_lower for fact in expected_facts))


def evaluate_mode(
    gold_queries: list[dict[str, Any]],
    *,
    mode_name: str,
    vectorstore_path: str,
    chunks_path: str,
    use_hybrid: bool,
    use_rerank: bool,
    final_k: int = 4,
    initial_k: int = 8,
    max_chunks_per_source: int = 2,
    debug_log_path: str | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    total_source_hit = 0
    total_mrr = 0.0
    total_top1 = 0
    total_fact_hit = 0
    total_all_facts_hit = 0

    category_totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "count": 0,
            "source_hit": 0,
            "mrr": 0.0,
            "top_1_correct": 0,
            "fact_hit": 0,
            "all_facts_hit": 0,
        }
    )

    for item in gold_queries:
        query_id = item["id"]
        category = item.get("category", "uncategorized")
        query = item["query"]
        expected_sources = item.get("expected_sources", [])
        expected_facts = item.get("expected_facts", [])

        docs = retrieve(
            query=query,
            final_k=final_k,
            initial_k=initial_k,
            max_chunks_per_source=max_chunks_per_source,
            vectorstore_path=vectorstore_path,
            chunks_path=chunks_path,
            use_hybrid=use_hybrid,
            use_rerank=use_rerank,
            debug_log_path=debug_log_path,
            debug_context={
                "query_id": query_id,
                "mode_name": mode_name,
            },
        )

        retrieved_sources = [
            str(doc.metadata.get("file_name", "unknown"))
            for doc in docs
        ]

        answer_text = generate_answer_from_docs(question=query, docs=docs)

        source_hit = hit_at_k(retrieved_sources, expected_sources)
        rr = reciprocal_rank(retrieved_sources, expected_sources)
        top1 = top_1_correct(retrieved_sources, expected_sources)
        fact_hit_value = fact_hit(answer_text, expected_facts)
        all_facts_hit_value = all_facts_hit(answer_text, expected_facts)

        total_source_hit += source_hit
        total_mrr += rr
        total_top1 += top1
        total_fact_hit += fact_hit_value
        total_all_facts_hit += all_facts_hit_value

        category_totals[category]["count"] += 1
        category_totals[category]["source_hit"] += source_hit
        category_totals[category]["mrr"] += rr
        category_totals[category]["top_1_correct"] += top1
        category_totals[category]["fact_hit"] += fact_hit_value
        category_totals[category]["all_facts_hit"] += all_facts_hit_value

        rows.append(
            {
                "id": query_id,
                "category": category,
                "query": query,
                "expected_sources": expected_sources,
                "retrieved_sources": retrieved_sources,
                "expected_facts": expected_facts,
                "answer": answer_text,
                "source_hit": source_hit,
                "mrr": rr,
                "top_1_correct": top1,
                "fact_hit": fact_hit_value,
                "all_facts_hit": all_facts_hit_value,
            }
        )

    n = len(gold_queries)

    summary = {
        "num_queries": n,
        "source_hit_rate": total_source_hit / n if n else 0.0,
        "mrr": total_mrr / n if n else 0.0,
        "top_1_accuracy": total_top1 / n if n else 0.0,
        "fact_hit_rate": total_fact_hit / n if n else 0.0,
        "all_facts_hit_rate": total_all_facts_hit / n if n else 0.0,
        "use_hybrid": use_hybrid,
        "use_rerank": use_rerank,
    }

    category_summary: dict[str, dict[str, float]] = {}
    for category, totals in category_totals.items():
        count = totals["count"]
        category_summary[category] = {
            "count": count,
            "source_hit_rate": totals["source_hit"] / count if count else 0.0,
            "mrr": totals["mrr"] / count if count else 0.0,
            "top_1_accuracy": totals["top_1_correct"] / count if count else 0.0,
            "fact_hit_rate": totals["fact_hit"] / count if count else 0.0,
            "all_facts_hit_rate": totals["all_facts_hit"] / count if count else 0.0,
        }

    return {
        "summary": summary,
        "category_summary": category_summary,
        "rows": rows,
    }


def print_mode_summary(mode_name: str, mode_result: dict[str, Any]) -> None:
    summary = mode_result["summary"]
    category_summary = mode_result["category_summary"]

    print(f"\n=== {mode_name} ===")
    print(f"queries              : {summary['num_queries']}")
    print(f"source_hit_rate      : {summary['source_hit_rate']:.3f}")
    print(f"mrr                  : {summary['mrr']:.3f}")
    print(f"top_1_accuracy       : {summary['top_1_accuracy']:.3f}")
    print(f"fact_hit_rate        : {summary['fact_hit_rate']:.3f}")
    print(f"all_facts_hit_rate   : {summary['all_facts_hit_rate']:.3f}")

    if category_summary:
        print("by_category:")
        for category, cat in category_summary.items():
            print(
                f"  - {category}: "
                f"count={cat['count']}, "
                f"source_hit_rate={cat['source_hit_rate']:.3f}, "
                f"top_1_accuracy={cat['top_1_accuracy']:.3f}, "
                f"fact_hit_rate={cat['fact_hit_rate']:.3f}, "
                f"all_facts_hit_rate={cat['all_facts_hit_rate']:.3f}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold-path", default="evals/retrieval_gold.yaml")
    parser.add_argument("--vectorstore-path", default="artifacts/faiss_index")
    parser.add_argument("--chunks-path", default="artifacts/chunks.jsonl")
    parser.add_argument("--output-path", default="evals/retrieval_eval_results.json")
    parser.add_argument("--final-k", type=int, default=4)
    parser.add_argument("--initial-k", type=int, default=8)
    parser.add_argument("--max-chunks-per-source", type=int, default=2)
    parser.add_argument("--debug-log-path", default="artifacts/evals/rerank_debug.jsonl")
    args = parser.parse_args()

    gold_queries = load_gold_queries(args.gold_path)

    results = {
        "dense_only": evaluate_mode(
            gold_queries,
            mode_name="dense_only",
            vectorstore_path=args.vectorstore_path,
            chunks_path=args.chunks_path,
            use_hybrid=False,
            use_rerank=False,
            final_k=args.final_k,
            initial_k=args.initial_k,
            max_chunks_per_source=args.max_chunks_per_source,
            debug_log_path=args.debug_log_path,
        ),
        "hybrid_only": evaluate_mode(
            gold_queries,
            mode_name="hybrid_only",
            vectorstore_path=args.vectorstore_path,
            chunks_path=args.chunks_path,
            use_hybrid=True,
            use_rerank=False,
            final_k=args.final_k,
            initial_k=args.initial_k,
            max_chunks_per_source=args.max_chunks_per_source,
            debug_log_path=args.debug_log_path,
        ),
        "hybrid_rerank": evaluate_mode(
            gold_queries,
            mode_name="hybrid_rerank",
            vectorstore_path=args.vectorstore_path,
            chunks_path=args.chunks_path,
            use_hybrid=True,
            use_rerank=True,
            final_k=args.final_k,
            initial_k=args.initial_k,
            max_chunks_per_source=args.max_chunks_per_source,
            debug_log_path=args.debug_log_path,
        ),
    }

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    for mode_name, mode_result in results.items():
        print_mode_summary(mode_name, mode_result)


if __name__ == "__main__":
    main()