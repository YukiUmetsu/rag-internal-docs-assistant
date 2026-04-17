# RAG Internal Docs Assistant
![CI](https://github.com/YukiUmetsu/rag-internal-docs-assistant/actions/workflows/ci.yml/badge.svg)

A Retrieval-Augmented Generation (RAG) system that answers questions using internal company documents across engineering, support, HR, and operations.

This project simulates a realistic company knowledge assistant with versioned documents, mixed formats (Markdown + PDF), and evaluation-driven development.

![Demo](./assets/search-demo.gif)

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
  API -->|search request| RETR[Retriever]
  API -->|ingest request| INGEST[Ingest API]
  RETR -->|FAISS| FAISS[(FAISS index + chunks)]
  RETR -->|pgvector| PG[(Postgres + pgvector)]
  INGEST --> DB[(Postgres metadata)]
  INGEST --> Redis[(Redis queue)]
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

## Retry and Idempotency

If the same ingest runs more than once, the corpus should not end up with
duplicate documents.

- each upload and ingest job is recorded in Postgres
- unchanged documents are skipped
- if a document changes, the old active version is marked inactive and the new
  version becomes active
- the original upload and job history stays available for debugging

These two tables do different jobs:

- `uploaded_files` = the file we received
- `source_documents` = the searchable document version we created from it

That is why the upload can stay in history even when a new document version
replaces the old active one.

That keeps re-runs safe and makes the corpus easier to trust. In a larger cloud
setup, I would put retry/backoff rules in the workflow or queue layer and send
jobs that keep failing into a dead-letter path. In practice, that means the
queue or workflow retries a job a few times with backoff, and if it still
fails, the message is moved aside for later inspection instead of blocking the
main queue.

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
- keeps persistent Docker volumes for uploads and corpus artifacts in the local
  demo
- defaults the retriever to Postgres unless you override `RETRIEVER_BACKEND`

The frontend is published on `http://localhost:4173` in this profile.
Use `make docker-prod-test` to validate the Compose configuration before
starting it.

Before shipping to production, I would also add authentication and
authorization so the admin pages and ingest endpoints are not open by default.
In practice, that usually means SSO or OIDC for people, plus role checks for
admin actions.

For a real deployment, the same containers can run on ECS/Fargate or Cloud Run.
In that setup, I would run migrations as a release step or one-off job before
the API starts serving traffic, and I would store uploads in object storage
instead of local Docker volumes.

- upload storage: Amazon S3, Google Cloud Storage, or Cloudflare R2
- database: Postgres for metadata, job state, and document indexes
- app runtime: ECS/Fargate or Cloud Run for the API and worker services

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

## What This Project Demonstrates

- Production-oriented RAG architecture with API, worker, queue, and database
- Async ingestion and job lifecycle design
- Retrieval evaluation with MRR and top-1 accuracy
- Handling versioned documents and duplicate sources
- A clear path from local containers to cloud deployment

## Current Limitations

- No authentication or multi-tenant isolation yet
- Local file storage is still used in the demo
- The search stack is designed for moderate scale, not huge corpus sizes
- Autoscaling is not part of the local demo environment

The deeper architecture, ingestion, evaluation, and production notes live in
[docs/architecture.md](docs/architecture.md),
[docs/ingestion.md](docs/ingestion.md),
[docs/evaluation.md](docs/evaluation.md), and
[docs/production.md](docs/production.md).

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

The detailed evaluation write-up lives in [docs/evaluation.md](docs/evaluation.md).

Short version:

- hybrid retrieval improved once dense and keyword results were merged with
  RRF
- canonical document grouping reduced near-duplicate noise
- a single-year metadata filter fixed the version/year failure mode
- the current `hybrid_rerank` gate reaches 1.000 MRR and 1.000 top-1 accuracy

## Learn More

- [Architecture](docs/architecture.md)
- [Ingestion & Idempotency](docs/ingestion.md)
- [Evaluation Details](docs/evaluation.md)
- [Production & Scaling](docs/production.md)

---

## 🧠 Author Notes

This project focuses on **quality over quantity**, emphasizing:

- realistic data
- controlled complexity
- explainable system behavior
