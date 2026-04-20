from __future__ import annotations

from langchain_core.documents import Document

from evals.run_groundedness_eval import answer_contains_refusal, answer_mentions_claim, score_claim


def test_answer_mentions_claim_supports_exact_match() -> None:
    answer = "The refund window is 30 days."
    claim = "The refund window is 30 days."

    assert answer_mentions_claim(answer, claim) is True


def test_answer_mentions_claim_supports_close_paraphrase() -> None:
    answer = "SEV2 means partial degradation."
    claim = "SEV2 indicates partial degradation."

    assert answer_mentions_claim(answer, claim) is True


def test_answer_contains_refusal_detects_abstention_language() -> None:
    answer = "I cannot answer that because there is not enough context."

    assert answer_contains_refusal(answer) is True


def test_score_claim_labels_supported_when_source_and_answer_align() -> None:
    docs = [
        Document(
            page_content="Refund window is 30 days.",
            metadata={"file_name": "refund_policy_2026.md"},
        )
    ]
    claim = {
        "id": "refund_window",
        "text": "The refund window is 30 days.",
        "type": "numeric",
        "critical": True,
        "supported_by": ["refund_policy_2026.md"],
        "conflict_with": [],
    }

    result = score_claim(
        answer="The refund window is 30 days.",
        claim=claim,
        retrieved_source_names={"refund_policy_2026.md"},
        retrieved_docs=docs,
        expected_behavior="answer",
    )

    assert result["label"] == "supported"


def test_score_claim_skips_unmentioned_optional_claim() -> None:
    docs = [
        Document(
            page_content="Refund policy applies to duplicate refund attempts.",
            metadata={"file_name": "refund_policy_2026.md"},
        )
    ]
    claim = {
        "id": "duplicate_refund_handling",
        "text": "Duplicate refund attempts should rely on idempotency keys and return existing refund results.",
        "type": "procedural",
        "critical": True,
        "optional": True,
        "supported_by": ["refund_policy_2026.md"],
        "conflict_with": [],
    }

    result = score_claim(
        answer="The playbook covers escalation handling and retries.",
        claim=claim,
        retrieved_source_names={"refund_policy_2026.md"},
        retrieved_docs=docs,
        expected_behavior="answer",
    )

    assert result["label"] == "skipped"
    assert result["triggered"] is False


def test_score_claim_labels_supported_for_optional_claim_when_mentioned() -> None:
    docs = [
        Document(
            page_content="Refund attempts should use idempotency keys.",
            metadata={"file_name": "refund_policy_2026.md"},
        )
    ]
    claim = {
        "id": "duplicate_refund_handling",
        "text": "Duplicate refund attempts should rely on idempotency keys and return existing refund results.",
        "type": "procedural",
        "critical": True,
        "optional": True,
        "supported_by": ["refund_policy_2026.md"],
        "conflict_with": [],
    }

    result = score_claim(
        answer="Duplicate refund attempts should rely on idempotency keys and return existing refund results.",
        claim=claim,
        retrieved_source_names={"refund_policy_2026.md"},
        retrieved_docs=docs,
        expected_behavior="answer",
    )

    assert result["label"] == "supported"
    assert result["triggered"] is True


def test_score_claim_labels_abstained_for_refusal_rows() -> None:
    docs: list[Document] = []
    claim = {
        "id": "no_hallucination",
        "text": "The answer should not invent a badge color policy.",
        "type": "factual",
        "critical": True,
        "supported_by": [],
        "conflict_with": [],
    }

    result = score_claim(
        answer="I could not find enough retrieved context to answer this question.",
        claim=claim,
        retrieved_source_names=set(),
        retrieved_docs=docs,
        expected_behavior="abstain",
    )

    assert result["label"] == "abstained"
