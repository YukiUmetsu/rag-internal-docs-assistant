from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = PROJECT_ROOT / "tests"
FIXTURES_ROOT = TESTS_ROOT / "fixtures" / "docs"


# Make sure `src/...` imports work when pytest runs from different locations.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session", autouse=True)
def test_env() -> None:
    """
    Safe defaults for test runs.

    Individual tests can still override these with monkeypatch or by passing
    explicit function arguments like `vectorstore_path=...`.
    """
    os.environ.setdefault("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    os.environ.setdefault("RERANK_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    os.environ.setdefault("VECTORSTORE_PATH", str(TESTS_ROOT / ".tmp" / "default_faiss_index"))


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def fixtures_root() -> Path:
    return FIXTURES_ROOT


@pytest.fixture
def test_index_path(tmp_path: Path) -> Path:
    """
    Fresh disposable FAISS path for each test.
    """
    return tmp_path / "faiss_test_index"


@pytest.fixture
def basic_ingest_fixture_paths(fixtures_root: Path) -> list[str]:
    """
    Small happy-path corpus for ingest integration tests.
    """
    return [
        str(fixtures_root / "policies" / "refund_policy_2026.md"),
        str(fixtures_root / "engineering" / "payment_flow.md"),
    ]


@pytest.fixture
def versioned_policy_fixture_paths(fixtures_root: Path) -> list[str]:
    """
    Useful for future retrieval/version-preference tests.
    """
    return [
        str(fixtures_root / "policies" / "refund_policy_2025.md"),
        str(fixtures_root / "policies" / "refund_policy_2026.md"),
    ]

@pytest.fixture
def test_chunks_path(tmp_path: Path) -> Path:
    return tmp_path / "chunks.jsonl"