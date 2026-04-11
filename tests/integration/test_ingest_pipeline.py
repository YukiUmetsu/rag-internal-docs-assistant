from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.rag import loader as loader_mod
from src.rag.ingest import run_full_update_from_paths
from src.rag.vectorstore import load_vectorstore


def test_full_ingest_creates_test_index(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        loader_mod,
        "DATA_DIR",
        _PROJECT_ROOT / "tests/fixtures/docs",
    )

    fixture_paths = [
        str(_PROJECT_ROOT / "tests/fixtures/docs/policies/refund_policy_2026.md"),
        str(_PROJECT_ROOT / "tests/fixtures/docs/engineering/payment_flow.md"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = Path(tmpdir) / "faiss_test_index"

        run_full_update_from_paths(
            fixture_paths,
            vectorstore_path=str(index_path),
        )

        assert index_path.is_dir()

        vectorstore = load_vectorstore(vectorstore_path=str(index_path))
        assert vectorstore is not None

    assert not Path(tmpdir).exists()
