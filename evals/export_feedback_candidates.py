from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import create_engine, text


DEFAULT_OUTPUT_PATH = Path("evals/feedback_candidates.yaml")


def build_draft_claim(reason_code: str, question: str) -> str:
    reason_code = reason_code.lower().strip()
    if reason_code == "abstain":
        return "The assistant should abstain when the available evidence is insufficient."
    if reason_code == "retrieval":
        return "The answer should use the relevant retrieved source for this question."
    if reason_code == "grounding":
        return "The answer should stay grounded in the retrieved sources."
    if reason_code == "policy":
        return "The answer should follow the relevant policy source."
    if reason_code == "tone":
        return "The answer should be clear and appropriately framed."
    return f"The answer should address: {question}"


def load_feedback_candidates(database_url: str, review_status: str) -> list[dict[str, Any]]:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT
                    af.id,
                    af.search_query_id,
                    af.request_kind,
                    af.verdict,
                    af.reason_code,
                    af.issue_category,
                    af.review_status,
                    af.comment,
                    af.reviewed_at,
                    sq.question,
                    sq.answer,
                    sq.requested_mode,
                    sq.mode_used
                FROM answer_feedback af
                JOIN search_queries sq ON sq.id = af.search_query_id
                WHERE af.review_status = :review_status
                ORDER BY af.created_at DESC, af.id DESC
                """
            ),
            {"review_status": review_status},
        ).mappings().all()

        source_rows = connection.execute(
            text(
                """
                SELECT query_id, file_name
                FROM search_results
                ORDER BY query_id ASC, rank ASC
                """
            )
        ).mappings().all()

    sources_by_query: dict[str, list[str]] = {}
    for row in source_rows:
        sources_by_query.setdefault(str(row["query_id"]), []).append(str(row["file_name"]))

    candidates: list[dict[str, Any]] = []
    for row in rows:
        question = str(row["question"])
        reason_code = str(row["reason_code"])
        search_query_id = str(row["search_query_id"])
        draft_claim = build_draft_claim(reason_code, question)
        expected_sources = sorted(dict.fromkeys(sources_by_query.get(search_query_id, [])))
        candidates.append(
            {
                "id": f"feedback_{row['id']}",
                "question": question,
                "category": str(row["issue_category"]),
                "expected_behavior": "abstain" if reason_code == "abstain" else "answer",
                "expected_sources": expected_sources,
                "claims": [
                    {
                        "id": "draft_feedback_claim",
                        "text": draft_claim,
                        "critical": True,
                        "optional": False,
                        "supported_by": expected_sources,
                    }
                ],
                "review_notes": row["comment"],
                "source_feedback": {
                    "feedback_id": str(row["id"]),
                    "search_query_id": search_query_id,
                    "request_kind": str(row["request_kind"]),
                    "verdict": str(row["verdict"]),
                    "reason_code": reason_code,
                    "review_status": str(row["review_status"]),
                    "reviewed_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
                    "requested_mode": str(row["requested_mode"]),
                    "mode_used": str(row["mode_used"]),
                },
            }
        )

    return candidates


def write_feedback_candidates(database_url: str, review_status: str, output_path: Path) -> Path:
    payload = {"queries": load_feedback_candidates(database_url, review_status)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=False)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export reviewed feedback as groundedness eval candidates.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--review-status", default="promoted")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    output_path = write_feedback_candidates(database_url, args.review_status, Path(args.output))
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
