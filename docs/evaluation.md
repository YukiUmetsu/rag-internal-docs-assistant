# Evaluation

The retrieval work in this project uses a committed gold set and baseline
comparisons.

## Baseline

FAISS-backed retrieval and the gold evaluation set measure whether the right
source document appears in the top results. Hybrid retrieval must handle:

- exact version questions
- year-sensitive policy questions
- near-duplicate document formats

## Query categories

The gold set covers the kinds of questions people usually ask in an internal
assistant:

- policy questions
- engineering questions
- incident questions
- HR questions

These categories matter because they force the retriever to handle both exact
terms and broader semantic matches.

## Why RRF helped

Reciprocal Rank Fusion (RRF) combines dense and keyword retrieval signals.

That helped because:

- dense retrieval can catch semantic matches
- keyword retrieval can catch exact terms
- RRF lets both contribute to the final ranking instead of forcing one to win

In practice, that improved the balance between semantic and lexical retrieval.

## Canonical document grouping

Some docs existed in more than one format, especially Markdown and PDF.

Without grouping, those near-duplicates could crowd out more useful sources.

Canonical grouping collapses those duplicates so the retriever sees a cleaner
candidate set and the final ranking has more diversity.

## Year filtering

The hardest failure mode was version-sensitive retrieval.

For queries that clearly name one year, the retriever applies a single-year
metadata filter before reranking. That keeps the system from preferring a
semantically similar but wrong-year policy.

Multi-year comparison queries are left unfiltered.

## Results

The `hybrid_rerank` gate reaches:

- `source_hit_rate = 1.000`
- `mrr = 1.000`
- `top_1_accuracy = 1.000`

## Operational value

The evaluation surfaces:

- retrieval failures
- ranking changes that improve or regress results
- baseline comparisons
- version-sensitive question handling

## Groundedness

Groundedness measures answer trustworthiness rather than source recall.

The concrete groundedness plan lives in
[docs/groundedness-eval.md](/Users/yukiumetsu/Documents/projects/demo/acme-company-assistant/docs/groundedness-eval.md).

That spec defines:

- a row schema for claim-level evaluation
- support / conflict / abstain labels
- answer-level groundedness formulas
- heuristic and judge-based scoring modes
- the release gates I would use for a production-style RAG demo

## Feedback Loop

User feedback is attached to the same request identifier used by search history
and tracing. The feedback record stores:

- the request kind
- the user verdict
- a normalized reason code
- the free-text comment
- the review status

Reviewed feedback can be promoted into candidate eval rows, keeping production
traffic and regression data connected through the same request anchor.

The export helper writes reviewed feedback into `evals/feedback_candidates.yaml`
for human curation before the rows are merged into a gold set.
