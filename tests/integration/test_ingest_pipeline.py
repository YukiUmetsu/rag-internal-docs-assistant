from __future__ import annotations

from pathlib import Path

import pytest

from src.rag.ingest import run_full_update_from_paths
from src.rag.vectorstore import load_vectorstore


def test_full_ingest_creates_test_index(
    basic_ingest_fixture_paths: list[str],
    test_index_path: Path,
) -> None:
    run_full_update_from_paths(
        basic_ingest_fixture_paths,
        vectorstore_path=str(test_index_path),
    )

    assert test_index_path.is_dir()

    vectorstore = load_vectorstore(vectorstore_path=str(test_index_path))
    assert vectorstore is not None


def test_full_ingest_raises_for_missing_file(test_index_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        run_full_update_from_paths(
            ["tests/fixtures/docs/does_not_exist.md"],
            vectorstore_path=str(test_index_path),
        )


def test_full_ingest_skips_unsupported_file_types(
    tmp_path: Path,
    basic_ingest_fixture_paths: list[str],
) -> None:
    unsupported_file = tmp_path / "notes.docx"
    unsupported_file.write_text("this should be ignored", encoding="utf-8")

    run_full_update_from_paths(
        [basic_ingest_fixture_paths[0], str(unsupported_file)],
        vectorstore_path=str(tmp_path / "faiss_test_index"),
    )

    vectorstore = load_vectorstore(vectorstore_path=str(tmp_path / "faiss_test_index"))
    assert vectorstore is not None