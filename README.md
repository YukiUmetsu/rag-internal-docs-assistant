# RAG Internal Docs Assistant

A production-style Retrieval-Augmented Generation (RAG) system that answers questions using internal company documents across engineering, support, HR, and operations.

This project simulates a realistic company knowledge assistant with versioned documents, mixed formats (Markdown + PDF), and evaluation-driven development.

---

## Development setup

- Install Docker Desktop.
- Copy `.env.example` to `.env` and set values when running LLM-backed commands.
- Build the app images: `make install`
- Run tests from the repo root: `make test`

For local non-Docker debugging, use the `local-*` Makefile targets.

```bash
make local-backend
make local-frontend
make local-test
```

The default Makefile targets use Docker.

---

## Web Demo

Run the Dockerized app:

```bash
make dev
```

Open `http://localhost:5173` and try:

- "What was the refund window in 2025?"
- "How many PTO days do employees get?"
- "When is manager approval required for refunds?"

The UI supports live generation, mock safe mode, and retrieval-only inspection. Mock mode is useful for demos when Groq quota is unavailable.

### Docker Web Demo

Stage 1 Docker support runs the existing FAISS-backed app only. It does not add Postgres, Redis, Celery, or pgvector yet.

```bash
make dev
```

Open `http://localhost:5173`. The frontend calls the backend at `http://localhost:8000`.

Useful Docker commands:

```bash
make logs-backend
make logs-frontend
make test
make stop
```

The dev compose stack bind-mounts the repo, including `data/` and `artifacts/`, so it uses the same FAISS index and chunk files as local development.

### LangSmith Observability

Set `LANGSMITH_API_KEY` to enable traces for backend chat and retrieval requests. The app defaults to the `acme-company-assistant-dev` project unless `LANGSMITH_PROJECT` is set.

Each trace captures:

- request mode, question length, and requested `final_k`
- retrieval latency, detected year, source count, unique source count, and source metadata
- generation metadata including context size, document count, and source files
- final mode used, answer length, warnings, and end-to-end latency

These fields are intended to support later LangSmith datasets and evaluators for correctness, groundedness, relevance, and retrieval relevance.

---

## 🚀 Overview

This system allows users to ask natural language questions such as:

- "What is the refund policy?"
- "How do we handle failed payments?"
- "What should we do during a payment failure incident?"
- "How many PTO days do employees get?"

The system retrieves relevant internal documents and generates grounded answers with citations.

---

## 🧠 Key Features

### 1. Multi-Domain Knowledge Base
Includes realistic internal documents from multiple domains:

- Engineering (payment systems)
- Support (playbooks)
- Policies (refund rules)
- HR (PTO policies)
- Incidents (runbooks)

---

### 2. Versioned Documents (Real-World Ambiguity)

Simulates real company scenarios with multiple versions:

- `refund_policy_2025.md`
- `refund_policy_2026.md`

Subtle differences force the system to choose the correct version.

---

### 3. Mixed Document Formats

Supports:

- Markdown (structured)
- PDF (semi-structured, noisy)

Example:
- `refund_policy_2026.md`
- `refund_policy_2026.pdf`

This introduces:
- formatting inconsistencies
- duplicate content
- parsing challenges

---

### 4. Realistic Failure Scenarios

The dataset intentionally includes:

- conflicting policies
- duplicate content across formats
- noisy PDF extraction
- ambiguous queries

This allows evaluation of real-world RAG failure modes.

---

### 5. Evaluation-Driven Development

The system is designed to evaluate:

- correctness
- groundedness
- relevance
- retrieval quality

Using structured evaluation datasets.

---

### 6. Full-Stack Demo

The repo includes a React + FastAPI demo app:

- clean assistant interface
- source citations
- retrieval debug panel
- live/mock/retrieval-only modes
- backend health and artifact status

---

### 7. Retrieval

- Query → embedding
- Retrieve top-k relevant chunks
- Apply filtering and ranking

---

### 8. Generation

- LLM generates answer using retrieved context
- Includes grounding in source documents

---

### 9. (Optional) Corrective RAG

- Detect weak retrieval
- Rewrite query
- Retry retrieval

---

## 🧪 Example Queries

### Policy Questions

- "What is the refund window?"
- "Do refunds over $1000 require approval?"

### Engineering Questions

- "How does the payment flow work?"
- "What are common payment errors?"

### Incident Questions

- "How do we debug a spike in payment failures?"
- "What is a SEV1 incident?"

### HR Questions

- "How many PTO days do employees get?"
- "Is jury duty paid?"

---

## ⚠️ Known Challenges (Intentional)

This project includes real-world challenges:

- outdated vs current documents
- duplicate content across formats
- semantic variations in wording
- noisy PDF extraction
- multi-domain ambiguity

---

## 🎯 Design Decisions

### Why Markdown + PDF?

To simulate real-world document ecosystems:
- clean structured docs
- messy exported documents
- duplicate knowledge sources

---

### Why Versioned Documents?

To test:
- retrieval accuracy
- ability to prefer newer policies
- handling conflicting information

---

### Why Limited Dataset?

The dataset is intentionally small but high-quality to:
- isolate failure modes
- enable clear evaluation
- avoid unnecessary complexity

---

## 🚀 Future Improvements

- Add LangSmith evaluation pipeline
- Add semantic caching (Redis)
- Introduce agentic workflows (LangGraph)
- Add multi-turn conversation support

---

## 📌 Goals

This project demonstrates:

- RAG system design
- real-world data challenges
- evaluation and iteration
- production-oriented thinking

---

## 🤝 Inspiration

Inspired by real-world internal knowledge assistants used in:

- engineering teams
- support operations
- HR systems

---

## Evaluation Story

(1) Dense retrieval was already strong, and hybrid retrieval was neutral on the initial dataset. Reranking improved exact-term and some ambiguous cases, but it still regressed version-sensitive ranking. The remaining issue appears to be that semantic reranking still over-prefers newer or semantically similar documents when the query requires an exact historical version.

(2) I observed that duplicate document formats (PDF vs Markdown) were dominating top retrieval results in some cases. I introduced canonical document grouping to collapse near-duplicates and improve result diversity, which improved version-sensitive retrieval performance.

(3) I replaced the simple dense-first hybrid merge with Reciprocal Rank Fusion (RRF), so dense and keyword retrieval could both influence candidate order. This improved the hybrid retrieval baseline, but reranking still exposed a specific weakness: when the query named an exact year, semantically similar documents from the wrong year could still outrank the correct historical policy.

(4) I added an explicit single-year metadata filter before reranking. When a query contains exactly one year, retrieval first constrains candidates to documents with matching `year` metadata, while multi-year comparison queries remain unfiltered. This resolved the version/year failure mode: on the current 11-query retrieval eval, `hybrid_rerank` improved to 1.000 MRR and 1.000 top-1 accuracy across latest-policy, exact-term, ambiguous, version-sensitive, and exact-year categories.

--

## 🧠 Author Notes

This project focuses on **quality over quantity**, emphasizing:

- realistic data
- controlled complexity
- explainable system behavior
