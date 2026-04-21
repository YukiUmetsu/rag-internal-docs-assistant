# Groundedness Evaluation

This evaluator measures whether the final answer stays faithful to the
retrieved evidence.

The goal is not just:

- did we fetch the right document?

It is:

- did the generated answer only make claims the retrieved context supports?
- did it avoid inventing details?
- did it refuse when the evidence was too weak?

## What gets scored

Each eval row contains one question, the retrieved sources, the generated answer,
and a set of atomic claims we expect the answer to make or avoid.

The important unit is the claim, not the whole paragraph.

### Claim labels

Each claim should receive one of these labels:

- `supported`
- `unsupported`
- `conflicting`
- `abstained`
- `skipped`

Use `supported` when the retrieved evidence explicitly contains the fact, or an
obvious paraphrase of it.

Use `unsupported` when the answer states something that is not grounded in the
retrieved context.

Use `conflicting` when the answer disagrees with the evidence, especially for
versioned or numeric facts.

Use `abstained` when the answer correctly refuses to state a fact because the
retrieved evidence is insufficient.

Use `skipped` when a claim is optional and the answer does not make that
claim. Skipped claims are excluded from the aggregate rates and do not affect
row pass/fail.

## Judge modes

The evaluator supports two scoring paths:

- `heuristic`: string and source-based checks only
- `judge`: LLM-based claim scoring over the retrieved context
- `hybrid`: LLM judge first, heuristic fallback if the judge call fails

Use the heuristic path for a fast regression gate. Use the judge path when the
claim requires semantic support, paraphrase handling, or multi-source synthesis.

## Row schema

The groundedness eval should live in `evals/groundedness_gold.yaml` and use this
shape:

```yaml
queries:
  - id: refund_window_2026
    category: version_sensitive
    query: What is the refund window?
    expected_sources:
      - refund_policy_2026.md
    answer_mode: live
    expected_answer_mode: live
    expected_behavior: answer
    claims:
      - id: refund_window
        text: The refund window is 30 days.
        type: factual
        critical: true
        support_mode: any
        supported_by:
          - refund_policy_2026.md
        conflict_with:
          - refund_policy_2025.md
      - id: refund_edge_case
        text: Duplicate refund attempts should rely on idempotency keys and return existing refund results.
        type: procedural
        optional: true
        critical: true
        supported_by:
          - refund_policy_2026.md
    abstain_if:
      - insufficient_context

```

Field meanings:

- `id`: stable row identifier
- `category`: evaluation bucket such as `exact_term`, `version_sensitive`, or `ambiguous`
- `query`: the user question
- `expected_sources`: sources that should be present in retrieval
- `answer_mode`: optional mode hint for the runner
- `expected_answer_mode`: the mode we expect the system to use
- `expected_behavior`: `answer` or `abstain`
- `claims`: atomic answer facts to score
- `abstain_if`: conditions under which abstention is considered correct

### Claim fields

- `id`: stable claim identifier
- `text`: the claim as written in the answer key
- `type`: `factual`, `numeric`, `version`, `procedural`, or `comparative`
- `critical`: whether the answer fails if this claim is unsupported
- `support_mode`: `any` when any listed source is enough, `all` when the full
  listed source set must be present
- `supported_by`: source files that should justify the claim
- `conflict_with`: source files or statements that contradict the claim
- `must_appear_in_answer`: optional boolean for exact-answer checks
- `optional`: when true, the claim is only scored if the answer makes that
  claim; otherwise the claim is labeled `skipped`

## Scoring formulas

Let:

- `S` = number of supported claims
- `U` = number of unsupported claims
- `C` = number of conflicting claims
- `A` = number of abstained claims
- `K` = number of skipped claims
- `T` = supported + unsupported + conflicting + abstained claims

Then:

- `supported_claim_rate = S / T`
- `unsupported_claim_rate = U / T`
- `conflict_rate = C / T`
- `abstain_rate = A / T`

A simple overall groundedness score is:

```text
groundedness_score = supported_claim_rate - conflict_rate - 0.5 * unsupported_claim_rate
```

That keeps conflicts expensive, unsupported claims costly, and supported claims
rewarded.

### Answer-level pass rule

An answer passes if all of the following are true:

- every critical claim is `supported`
- no claim is `conflicting`
- `groundedness_score >= threshold`
- skipped claims do not affect the pass rule

A threshold of `0.80` is a reasonable default.

### Abstention metrics

Groundedness should also track whether the assistant knows when to stop:

- `appropriate_abstain_rate`
- `overconfident_answer_rate`

Definitions:

- `appropriate_abstain_rate = correct_abstains / rows_that_should_abstain`
- `overconfident_answer_rate = unsupported_answers_on_should_abstain_rows / rows_that_should_abstain`

`appropriate_abstain_rate` should increase.
`overconfident_answer_rate` should decrease.

## Judge strategy

Score groundedness in layers:

1. Deterministic checks for exact numbers, years, and cited document names.
2. String or span matching for obvious factual statements.
3. LLM judge scoring for paraphrases, multi-source support, and contradiction detection.
4. Human spot checks on a small sample each run.

That mix keeps the system explainable while still covering fuzzy language.

## How to use it

The groundedness eval uses the same gold set as retrieval evals or a sibling
gold set designed for answer faithfulness.

Recommended reporting:

- overall groundedness score
- claim support rate
- conflict rate
- skipped claim count
- appropriate abstain rate
- per-category breakdown

## Running

Run the evaluator from the repository root:

```bash
make groundedness-eval
```

For a local Python run without Docker:

```bash
make local-groundedness-eval
```

The runner reads `evals/groundedness_gold.yaml` and writes results to
`artifacts/evals/groundedness_eval_results.json`.

The command uses live answer generation by default and falls back to the mock
answer path if the live generation step fails.

To enable the LLM judge:

```bash
make groundedness-eval GROUNDEDNESS_JUDGE_MODE=judge GROQ_JUDGE_MODEL_NAME=your-model-name
```

or run the Python entrypoint directly with `--judge-mode judge` or
`--judge-mode hybrid`.

If `GROQ_JUDGE_MODEL_NAME` is unset, the judge uses
`meta-llama/llama-4-scout-17b-16e-instruct`.

The local target assumes the retrieval and rerank models are already cached in
the environment. If those models are not cached, run the Docker target instead
so the containerized environment can provide the full dependency set.
