# Evaluation

The retrieval work in this project was driven by a committed gold set and a
baseline-first workflow.

## Starting point

The project began with FAISS-backed retrieval and a gold evaluation set that
measured whether the right source document appeared in the top results.

The initial hybrid retriever was decent, but it was not yet strong enough on:

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

I replaced a simple dense-first merge with Reciprocal Rank Fusion (RRF).

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

For queries that clearly name one year, the retriever now applies a single-year
metadata filter before reranking. That keeps the system from preferring a
semantically similar but wrong-year policy.

Multi-year comparison queries are left unfiltered.

## Current result

The current `hybrid_rerank` gate reaches:

- `source_hit_rate = 1.000`
- `mrr = 1.000`
- `top_1_accuracy = 1.000`

That makes the evaluation story easy to explain:

- baseline first
- fix the failure mode
- compare again
- keep the winning change only if it improves the gold set

## Why this is useful in interviews

This shows more than “I built a retriever.”

It shows:

- I can diagnose retrieval failures
- I can explain why a ranking change helps
- I can keep a baseline and measure real gains
- I can protect version-sensitive questions, which matter in internal docs
