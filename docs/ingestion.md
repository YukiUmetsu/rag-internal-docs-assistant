# Ingestion

The ingest pipeline is built to be safe to rerun and easy to inspect.

## Job lifecycle

Ingest jobs move through four states:

- `queued`
- `running`
- `succeeded`
- `failed`

The API creates the job first, then Celery runs it in the background. The admin
UI reads the same job state from Postgres.

## What gets ingested

The worker can ingest:

- mounted documents from the repo data directory
- uploaded `.md` and `.pdf` files

Both paths end up in the same searchable document and chunk tables.

## Idempotency

Re-running ingest should not create duplicate corpus rows.

The current behavior is:

- unchanged documents are skipped
- if a document changed, the old active version is marked inactive
- the new version becomes active
- the original upload and job history stays in Postgres

This means the same ingest can run more than once without quietly duplicating
the corpus.

## Versioning

The main versioning rule is simple:

- `is_active = true` means the row is the current searchable version
- `checksum` tells us whether the content changed

For mounted files, the stable key is the file path.
For uploads, the stable key is the upload record id.

If the same key appears again with a different checksum, the old active row is
retired and the new row becomes active.

## Retries

Today the worker flow is intentionally simple. In a larger cloud setup, retry
policy would usually live in the workflow or queue layer:

- retry temporary failures with backoff
- stop after a retry limit
- move poisoned jobs to a dead-letter path

That keeps failures visible without blocking the main queue forever.

## Why this matters

This setup keeps the corpus trustworthy:

- uploads stay traceable
- jobs stay auditable
- reingest stays safe
- the active corpus stays clean

That is the foundation the retriever depends on later.
