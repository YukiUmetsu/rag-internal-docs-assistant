# Production and Scaling

This project already has a strong local and production-like container setup.
The next step is a real cloud deployment.

## What production should look like

The app should keep the same basic contract in production:

- API service for chat, uploads, ingestion control, and admin reads
- worker service for background ingest
- Postgres for job state, metadata, documents, and search history
- Redis or a managed queue for asynchronous work

That means the application logic stays the same while the infrastructure
becomes managed and more scalable.

## Deployment targets

Good deployment targets for the current shape of the app are:

- ECS/Fargate
- Cloud Run
- Fly.io
- Render
- Railway

The main app contract stays the same:

- API service
- worker service
- Postgres
- Redis or a managed queue

## Migrations

Before serving traffic, migrations should run as a release step or one-off job.
That keeps schema changes explicit instead of hidden inside app startup.

I would treat schema migration as part of the deploy pipeline, not part of
request handling.

## Upload storage

The local Docker volumes are fine for development, but production should use
object storage for uploaded files and corpus artifacts.

Good options include:

- Amazon S3
- Google Cloud Storage
- Cloudflare R2

The database would keep metadata and object keys, not the raw file bytes.

That lets the app scale uploads independently from the container filesystem.

## Queue and retries

For larger-scale ingest, the queue/workflow layer should own retries and
backoff.

Useful production patterns:

- managed queue transport
- retry with backoff
- capped attempts
- dead-letter handling
- job status stored in Postgres

In practice, the worker should only be responsible for one attempt at a time.
If the attempt fails, the workflow or queue layer decides whether to retry and
how long to wait before the next attempt.

For more durable orchestration, the most useful options are:

- Temporal for resumable workflows and explicit activity retries
- AWS Step Functions for managed state machines and retries
- Google Cloud Workflows for serverless orchestration

Those tools make it easier to keep job progress visible while still allowing the
work to retry safely.

## Search scaling

Today Postgres handles keyword search and vector search together. That works
well for this project, but it may not stay the best shape forever.

If Postgres becomes the bottleneck, the next step is to split the search layer:

- keep Postgres for job state, uploads, and metadata
- move keyword search to a dedicated search engine
- move vector search to a dedicated vector service
- keep the ingest pipeline writing both indexes
- keep the retrieval contract stable so the app still merges and reranks
  results the same way

Possible concrete search backends:

- keyword search: OpenSearch or Elasticsearch
- vector search: Pinecone, Weaviate, or another vector store

That split is useful when a single Postgres instance starts carrying too much
read pressure or the search layer needs independent scaling.

The big idea is not to change what the user experiences. It is to let the
backing search systems scale independently behind the same API.

## Observability

OpenTelemetry is the right starting point for production observability.

From there, I would want:

- traces across API, worker, and retrieval
- logs with job ids and query ids
- metrics for latency, retries, queue depth, and failure rates
- alerts for failed ingest, slow search, and backlog growth

Operationally, I would watch:

- ingest duration
- job failure rate
- queue depth
- retry count
- retrieval latency
- top queries by volume
- corpus health counts
- backend selection and fallback rate

The goal is to make it obvious when the system is slow, unhealthy, or falling
back to the wrong path.

That is enough to debug real production issues without overcomplicating the
stack too early.
