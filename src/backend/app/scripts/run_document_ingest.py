from __future__ import annotations

import argparse
import time

from src.backend.app.core.corpus import count_active_corpus_rows
from src.backend.app.core.ingest_jobs import enqueue_document_ingest_job, get_ingest_job
from src.backend.app.core.settings import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enqueue and wait for a document ingest job.")
    parser.add_argument("--source-type", default="mounted_data")
    parser.add_argument("--job-mode", choices=["full", "partial"], default="full")
    parser.add_argument("--requested-paths", nargs="*", default=["data"])
    parser.add_argument("--uploaded-file-ids", nargs="*", default=[])
    parser.add_argument(
        "--skip-if-populated",
        dest="skip_if_populated",
        action="store_true",
        help="Do nothing when an active corpus already exists.",
    )
    parser.add_argument(
        "--no-skip-if-populated",
        dest="skip_if_populated",
        action="store_false",
        help="Force a new ingest job even when the active corpus already exists.",
    )
    parser.add_argument("--wait", dest="wait", action="store_true")
    parser.add_argument("--no-wait", dest="wait", action="store_false")
    parser.set_defaults(wait=True)
    parser.set_defaults(skip_if_populated=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()

    if args.skip_if_populated:
        counts = count_active_corpus_rows(settings.database_url)
        if counts["source_documents"] > 0:
            print(
                "Active corpus already exists "
                f"({counts['source_documents']} source document(s), {counts['document_chunks']} chunk(s))."
            )
            return

    job = enqueue_document_ingest_job(
        settings.database_url,
        source_type=args.source_type,
        job_mode=args.job_mode,
        requested_paths=args.requested_paths,
        uploaded_file_ids=args.uploaded_file_ids,
    )
    print(f"Queued ingest job {job.id} ({job.job_mode})")

    if not args.wait:
        return

    deadline = time.monotonic() + 300
    latest = job
    while time.monotonic() < deadline:
        latest = get_ingest_job(settings.database_url, job.id)
        print(f"{latest.id}: {latest.status}")
        if latest.status in {"succeeded", "failed"}:
            break
        time.sleep(1.0)

    if latest.status != "succeeded":
        raise SystemExit(f"Ingest job {job.id} finished with status {latest.status}")

    print(latest.result_message or "Ingest completed.")


if __name__ == "__main__":
    main()
