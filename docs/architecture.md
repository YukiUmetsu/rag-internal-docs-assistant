# Architecture

This project is split into a few clear pieces so retrieval, ingest, and admin
work can evolve independently.

## API vs worker

The FastAPI app handles request/response work:

- chat and retrieval requests
- upload requests
- ingest job creation and status reads
- admin pages and summary endpoints

The Celery worker handles slower background work:

- validation-only ingest jobs
- full corpus ingest
- processing uploaded files
- writing documents and chunks to Postgres

That split keeps the API responsive while document processing happens in the
background.

## Ingestion flow

The ingestion path starts when the API creates an ingest job in Postgres.

1. The API records the job with `queued` status.
2. The job is sent to Redis through Celery.
3. The worker marks the job `running`.
4. The worker loads mounted files and/or uploaded files.
5. The worker creates or updates searchable document rows.
6. The worker splits documents into chunks and stores embeddings.
7. The worker marks the job `succeeded` or `failed`.

## Retrieval flow

The search path is separate from ingest:

1. The API receives a question.
2. The app chooses the retrieval backend from `RETRIEVER_BACKEND`.
3. FAISS reads from the file-based index, or Postgres reads from pgvector and
   full-text search.
4. The retriever returns ranked chunks.
5. The app reranks and formats the response.

## Agentic tool routing

`POST /api/agent/chat` sits beside the existing chat and retrieve endpoints. It
uses a small LangChain tool-calling layer to route questions to read-only tools:
internal document retrieval, corpus stats, recent ingest jobs, and recent search
history. The agent is bounded to a small number of calls and returns its tool
trace so behavior stays inspectable.

## Postgres vs pgvector

Postgres does more than one job in this app:

- stores uploads and ingest jobs
- stores search history and admin history
- stores source documents and chunk rows
- stores job status and corpus metadata

pgvector is the part of Postgres that stores the dense embedding values for
similarity search. Keyword search still uses Postgres full-text search through
`tsvector`.

So in practice:

- Postgres = durable app data and search metadata
- pgvector = dense vector search inside Postgres
- `tsvector` = keyword search inside Postgres

## Redis + Celery

Redis is the queue transport for background jobs.

Celery reads jobs from Redis and runs them in the worker process. This keeps
short API requests separate from long-running ingest work.

For local development, Redis + Celery is enough. In production, the same job
shape can be moved to a managed queue or workflow system without changing the
core app contract.

## Data model

The main tables are:

- `uploaded_files` - raw upload records
- `ingest_jobs` - ingest job state and execution history
- `ingest_job_uploads` - which uploads belong to which job
- `source_documents` - searchable document versions
- `document_chunks` - chunk-level retrieval rows
- `search_queries` - question history
- `search_results` - returned source rows for each query

The important split is:

- `uploaded_files` = the file we received
- `source_documents` = the searchable version created from it

That separation makes it easier to keep provenance, versioning, and search
state clean.

## Corpus shape

The corpus is intentionally mixed so the retriever has to deal with the kinds of
content internal tools usually see:

- multiple business domains
- versioned policy documents
- Markdown and PDF formats
- duplicate content across formats

That mix matters because it creates realistic retrieval problems:

- choosing the right version
- handling near-duplicate sources
- dealing with noisy PDF extraction
- keeping the active corpus clean over time
