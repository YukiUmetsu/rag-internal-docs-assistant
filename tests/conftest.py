from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

from src.backend.app.core.settings import get_settings


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
    os.environ.setdefault("EMBEDDING_DIMENSION", "384")
    os.environ.setdefault("RERANK_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    os.environ.setdefault("VECTORSTORE_PATH", str(TESTS_ROOT / ".tmp" / "default_faiss_index"))
    os.environ["RETRIEVER_BACKEND"] = "faiss"
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_backend_logging_state() -> None:
    """
    Keep backend loggers in a predictable state across the full suite.

    Some tests or imported modules can mutate logging globals, which can make
    later caplog assertions flaky when the entire suite runs together.
    """
    logging.disable(logging.NOTSET)
    for logger_name in (
        "src.backend.app.api.admin_routes",
        "src.backend.app.api.public_routes",
        "src.backend.app.core.feedback",
        "src.backend.app.core.search_history",
        "src.backend.app.core.uploads",
    ):
        logger = logging.getLogger(logger_name)
        logger.disabled = False
        logger.propagate = True
        logger.setLevel(logging.NOTSET)
    yield


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
