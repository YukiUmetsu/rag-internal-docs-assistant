from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.rag.ingest import run_full_update_from_paths
from src.rag.vectorstore import load_vectorstore


def test_full_ingest_creates_test_index(tmp_path: Path) -> None:
    docs_root = _PROJECT_ROOT / "tests" / "fixtures" / "docs"
    fixture_paths = [
        str(docs_root / "policies" / "refund_policy_2026.md"),
        str(docs_root / "engineering" / "payment_flow.md"),
    ]
    index_path = tmp_path / "faiss_test_index"

    run_full_update_from_paths(fixture_paths, vectorstore_path=str(index_path))

    assert index_path.is_dir()
    assert load_vectorstore(vectorstore_path=str(index_path)) is not None
