# Retrieval Baselines

This directory stores committed retrieval quality baselines used during the
incremental pgvector migration.

`faiss_hybrid_rerank.json` captures the current FAISS-backed `hybrid_rerank`
behavior with answer generation skipped. It is the safety net for later
Postgres/pgvector work.

Expected `hybrid_rerank` metrics:

- `source_hit_rate = 1.000`
- `mrr = 1.000`
- `top_1_accuracy = 1.000`

Regenerate intentionally with:

```bash
make eval-baseline
```

Compare current results to the committed baseline with:

```bash
make eval-compare
```
