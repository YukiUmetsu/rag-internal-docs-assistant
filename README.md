# RAG Internal Docs Assistant

A production-style Retrieval-Augmented Generation (RAG) system that answers questions using internal company documents across engineering, support, HR, and operations.

This project simulates a realistic company knowledge assistant with versioned documents, mixed formats (Markdown + PDF), and evaluation-driven development.

## Project Highlights

- Postgres/pgvector retrieval with FAISS fallback and a one-command local switch.
- Async ingestion with Redis + Celery for mounted docs and uploaded files.
- Eval-gated retriever parity against a committed FAISS baseline.
- Admin UI for uploads, ingest jobs, documents, search history, and corpus health.
- Docker dev and production-like profiles for consistent local and deployment-style runs.
- Backend and frontend tests for upload, ingest, retrieval, and admin workflows.

## Architecture

```mermaid
flowchart LR
  UI[React Frontend] --> API[FastAPI API]
  API --> RETR[Retriever]
  RETR -->|FAISS| FAISS[(FAISS index + chunks)]
  RETR -->|pgvector| PG[(Postgres + pgvector)]
  API --> DB[(Postgres metadata)]
  API --> Redis[(Redis queue)]
  Redis --> Worker[Celery Worker]
  Worker --> DB
  Worker --> PG
  Worker --> Artifacts[(Uploads + corpus artifacts)]
  Eval[Retrieval Eval] --> RETR
```

## Results

- Retrieval quality is checked against a committed FAISS baseline.
- The Postgres retriever matches the FAISS baseline on the current retrieval eval gate.
- The admin dashboard surfaces live corpus, ingest, and usage metrics instead of static demo data.

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

### Switching the retriever locally

The app can read from either FAISS or Postgres/pgvector. Switch it with:

```bash
make retriever-faiss
make retriever-postgres
```

These commands update `RETRIEVER_BACKEND` in `.env` and restart the API and
worker containers so the new retriever takes effect right away. `make
retriever-postgres` also checks whether the active Postgres corpus is empty by
default, and if it is, it runs the mounted-document ingest pipeline for you.

Use `faiss` if you want the original file-based retriever. Use `postgres` if
you want the database-backed retriever that reads from `source_documents` and
`document_chunks`.

For quality checks, the Postgres path is the one exercised by `make docker-eval`.
The FAISS path remains the fallback and the baseline reference point.

### Production-like Docker profile

When you want the stack to behave more like a deployment and less like a live
development workspace, use the production-like Compose profile:

```bash
make docker-prod-up
make docker-prod-logs
make docker-prod-down
```

This profile:

- runs the API and worker without reload
- serves the frontend from built assets instead of the Vite dev server
- avoids bind-mounting the repo source into the runtime containers
- keeps persistent Docker volumes for uploads and corpus artifacts
- defaults the retriever to Postgres unless you override `RETRIEVER_BACKEND`

The frontend is published on `http://localhost:4173` in this profile.
Use `make docker-prod-test` to validate the Compose configuration before
starting it.

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

The Dockerized web demo now includes the full app stack:

- API
- frontend
- Postgres with pgvector
- Redis
- Celery worker

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

The current stack is local-first, but it can scale cleanly into cloud infrastructure.

### Reference cloud stack

If we moved this into a production cloud environment, I would keep the same
application contract and swap the plumbing underneath it:

- queue transport: Amazon SQS, Google Pub/Sub, or Azure Service Bus
- workflow/orchestration layer: Temporal, AWS Step Functions, or Google Cloud
  Workflows
- worker autoscaling: cloud-native autoscaling based on queue depth and CPU
- durable job state: Postgres with explicit status transitions and attempt
  history

The API would still create a job row first, then publish work. The worker would
claim the job, update state to `running`, process the document, and finish with
`succeeded` or `failed`. The difference is that the queue and workflow engine
become managed services, while Postgres remains the source of truth for the UI
and audit trail.

### Worker scaling, retries, and status tracking

For long-running ingest work, the cleanest pattern is:

- keep a job record in Postgres with `queued`, `running`, `succeeded`, and
  `failed`
- store `attempt_count`, `last_error`, `started_at`, `finished_at`, and an
  external execution id
- use workflow-level retries for transient failures
- use a dead-letter queue or failed execution bucket for poisoned jobs
- keep the job id stable, and treat each worker attempt as just one execution
  of that job

Temporal is a strong fit when we want durable workflows with resumable state and
explicit retries. Step Functions and Cloud Workflows are also good when the
workflow is mostly an orchestrated series of cloud calls and we want managed
retry/backoff behavior without running the orchestration layer ourselves.

### Scale keyword and vector search independently

The search path should be able to grow without changing the product contract:

- keep Postgres full-text search for keyword matches while it remains cheap and
  fast
- keep pgvector in Postgres while the corpus and latency targets are moderate
- split the serving path from the ingest path when query volume grows
- keep the merge and rerank logic stable so the retrieval behavior does not
  change even if the backing stores do

If the corpus eventually outgrows a single Postgres deployment, the next step is
to separate the keyword and vector read paths so each can scale and cache
independently.

If Postgres itself becomes the bottleneck because it is carrying both keyword
and vector search, I would split it further:

- keep Postgres for job state, uploads, and document metadata
- move keyword search to a dedicated search engine, for example OpenSearch
  or Elasticsearch
- move vector search to a dedicated vector service, for example Pinecone or
  Weaviate
- keep the ingest pipeline responsible for writing both indexes
- keep the retrieval contract stable so the application still merges and reranks
  results the same way

### Improve observability

For production observability, I would add OpenTelemetry first and keep the rest
of the stack simple:

- OpenTelemetry instrumentation in the API, worker, and retriever
- OpenTelemetry Collector to receive and export telemetry
- a metrics backend for dashboards and alerts
- a log backend for application and worker logs
- a trace backend for request and job tracing

The most useful signals for this app are:

- ingest duration
- queue depth
- retry count
- failure rate by job type
- retrieval latency
- top queries by volume
- corpus health counts
- backend selection and fallback rate

I would also keep structured logs with `job_id`, `query_id`, backend, latency,
status, and error text so traces and logs can be correlated quickly when a job
misbehaves. Alerts should cover failed ingests, missing corpus data, latency
regressions, and queue backlog.

LangSmith remains useful for retrieval debugging, but production observability
should also cover queue health and system-level SLOs.

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
