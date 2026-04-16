from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from src.backend.app.main import app
from src.rag.retrieve import retrieve


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def ensure_retrieval_schema() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for postgres retrieval tests")

    alembic_ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(alembic_ini_path))
    command.upgrade(config, "head")


def _wait_for_ingest_job(job_id: str, *, timeout_seconds: float = 120.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, object] | None = None

    while time.monotonic() < deadline:
        response = client.get(f"/api/ingest/jobs/{job_id}")
        assert response.status_code == 200
        latest = response.json()
        if latest["status"] in {"succeeded", "failed"}:
            return latest
        time.sleep(0.5)

    raise AssertionError(f"Ingest job {job_id} did not finish in time: {latest}")


def _ingest_basic_corpus(basic_ingest_fixture_paths: list[str]) -> None:
    response = client.post(
        "/api/ingest/jobs",
        json={
            "source_type": "mounted_data",
            "job_mode": "full",
            "requested_paths": basic_ingest_fixture_paths,
            "uploaded_file_ids": [],
        },
    )
    assert response.status_code == 202
    job_id = response.json()["id"]
    latest = _wait_for_ingest_job(job_id)
    assert latest["status"] == "succeeded"


def test_postgres_retriever_returns_refund_policy_doc(
    basic_ingest_fixture_paths: list[str],
) -> None:
    _ingest_basic_corpus(basic_ingest_fixture_paths)

    results = retrieve(
        query="What is the refund window in 2026?",
        final_k=4,
        initial_k=8,
        max_chunks_per_source=2,
        retriever_backend="postgres",
        use_hybrid=True,
        use_rerank=True,
    )

    assert results
    assert any(
        "refund_policy_2026.md" == str(doc.metadata.get("file_name"))
        for doc in results
    )


def test_postgres_retriever_returns_engineering_doc(
    basic_ingest_fixture_paths: list[str],
) -> None:
    _ingest_basic_corpus(basic_ingest_fixture_paths)

    results = retrieve(
        query="How many retry attempts are allowed?",
        final_k=4,
        initial_k=8,
        max_chunks_per_source=2,
        retriever_backend="postgres",
        use_hybrid=True,
        use_rerank=False,
    )

    assert results
    assert any(
        "payment_flow.md" == str(doc.metadata.get("file_name"))
        for doc in results
    )


def test_postgres_retriever_overwrites_stale_chunk_metadata(
    basic_ingest_fixture_paths: list[str],
) -> None:
    _ingest_basic_corpus(basic_ingest_fixture_paths)

    database_url = os.getenv("DATABASE_URL")
    assert database_url is not None
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE document_chunks
                SET chunk_metadata = jsonb_set(
                    jsonb_set(
                        chunk_metadata,
                        '{file_name}',
                        '"stale-name.md"'
                    ),
                    '{domain}',
                    '"stale-domain"'
                )
                WHERE chunk_metadata->>'file_name' = 'payment_flow.md'
                """
            )
        )

    results = retrieve(
        query="How many retry attempts are allowed?",
        final_k=4,
        initial_k=8,
        max_chunks_per_source=2,
        retriever_backend="postgres",
        use_hybrid=True,
        use_rerank=False,
    )

    assert results
    assert any(
        doc.metadata.get("file_name") == "payment_flow.md"
        and doc.metadata.get("domain") == "engineering"
        for doc in results
    )
