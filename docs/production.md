# Production and Scaling

This project already has a strong local and production-like container setup.
The next step is a real cloud deployment.

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

## Upload storage

The local Docker volumes are fine for development, but production should use
object storage for uploaded files and corpus artifacts.

Good options include:

- Amazon S3
- Google Cloud Storage
- Cloudflare R2

The database would keep metadata and object keys, not the raw file bytes.

## Queue and retries

For larger-scale ingest, the queue/workflow layer should own retries and
backoff.

Useful production patterns:

- managed queue transport
- retry with backoff
- capped attempts
- dead-letter handling
- job status stored in Postgres

## Search scaling

Today Postgres handles keyword search and vector search together. That works
well for this project, but it may not stay the best shape forever.

If Postgres becomes the bottleneck, the next step is to split the search layer:

- keep Postgres for job state, uploads, and metadata
- move keyword search to a dedicated search engine
- move vector search to a dedicated vector service
- keep the ingest pipeline writing both indexes

## Observability

OpenTelemetry is the right starting point for production observability.

From there, I would want:

- traces across API, worker, and retrieval
- logs with job ids and query ids
- metrics for latency, retries, queue depth, and failure rates
- alerts for failed ingest, slow search, and backlog growth

That is enough to debug real production issues without overcomplicating the
stack too early.
