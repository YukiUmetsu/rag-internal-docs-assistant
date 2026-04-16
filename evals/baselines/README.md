# Retrieval Baselines

This directory stores committed retrieval-quality snapshots that we use to
protect search quality while the app migrates from FAISS to Postgres/pgvector.

## What this is for

The app now has two retrieval backends:

- `faiss`
- `postgres`

We keep a committed FAISS baseline so we can answer a simple question:

> Does the new Postgres retriever return the same good sources as the current
> FAISS retriever on the gold eval set?

That matters because retrieval can look “fine” on a couple of ad hoc queries
while still regressing on important cases like exact terms, year-sensitive
questions, or policy version lookups.

If you want to switch retriever types locally, see the main [README.md](/Users/yukiumetsu/Documents/projects/demo/acme-company-assistant/README.md) for the `RETRIEVER_BACKEND` setup and the restart step required for Docker.
If you just want the one-command switch, use `make retriever-faiss` or `make retriever-postgres` from the repo root.

## Baseline file

`faiss_hybrid_rerank.json` is the saved result of the current FAISS-backed
`hybrid_rerank` mode with answer generation skipped. It is the reference point
for later comparisons.

Expected `hybrid_rerank` metrics:

- `source_hit_rate = 1.000`
- `mrr = 1.000`
- `top_1_accuracy = 1.000`

## What the eval command does

`make docker-eval` runs the retrieval evals inside Docker using the Postgres
retriever, then compares those results against the committed FAISS baseline.

In plain English, it does this:

1. starts from the gold queries in `evals/retrieval_gold.yaml`
2. runs the app’s retrieval pipeline for each query
3. uses `RETRIEVER_BACKEND=postgres`
4. skips answer generation so the check stays focused on retrieval quality
5. verifies the summary metrics meet the required thresholds
6. compares each query’s retrieved sources to the FAISS baseline
7. fails if any gold query regresses

## Why `docker-eval` matters

This is the gate that lets us move from “the Postgres retriever seems to work”
to “the Postgres retriever is safe enough to become the default.”

It protects the transition in two ways:

- **global metrics**: the overall hit rate, MRR, and top-1 accuracy must stay
  at the expected level
- **per-query behavior**: individual gold queries must not fall behind the
  committed FAISS baseline

That second check is important. Averages can hide regressions in specific
queries, and those are usually the ones that matter in practice.

## How to run it

Compare the Postgres retriever against the committed FAISS baseline:

```bash
make docker-eval
```

Compare the current FAISS evaluation results to the baseline:

```bash
make eval-compare
```

Regenerate the FAISS baseline intentionally only when you mean to bless a new
reference point:

```bash
make eval-baseline
```

## What success looks like

When the eval passes, you should see:

- `source_hit_rate = 1.000`
- `mrr = 1.000`
- `top_1_accuracy = 1.000`
- baseline comparison passed

When it fails, the output should tell you which query regressed and show the
expected versus retrieved sources. That’s the signal to inspect the retrieval
change before promoting it.
