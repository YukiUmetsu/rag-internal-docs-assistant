from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.rag import loader as loader_mod


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "data"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(loader_mod, "DATA_DIR", root)
    return root


def test_loader_extracts_metadata_from_policy_filename(data_dir: Path) -> None:
    policies = data_dir / "policies"
    policies.mkdir(parents=True, exist_ok=True)
    path = policies / "refund_policy_2026.md"
    path.write_text("# Refund policy\n", encoding="utf-8")

    docs = loader_mod.load_markdown(path)

    assert len(docs) == 1
    meta = docs[0].metadata
    assert meta["year"] == "2026"
    assert meta["topic"] == "refund_policy"
    assert meta["domain"] == "policies"
    assert meta["file_type"] == "md"
    assert meta["file_name"] == "refund_policy_2026.md"
    assert meta["source"] == str(path)
    assert meta["source_doc_id"] == loader_mod.make_source_doc_id(path)


def test_loader_extracts_metadata_from_engineering_doc(data_dir: Path) -> None:
    engineering = data_dir / "engineering"
    engineering.mkdir(parents=True, exist_ok=True)
    path = engineering / "architecture_overview.md"
    path.write_text("# Architecture\n", encoding="utf-8")

    docs = loader_mod.load_markdown(path)

    assert len(docs) == 1
    meta = docs[0].metadata
    assert meta["year"] is None
    assert meta["topic"] == "architecture_overview"
    assert meta["domain"] == "engineering"
    assert meta["source_doc_id"] == loader_mod.make_source_doc_id(path)


@patch.object(loader_mod, "PyPDFLoader")
def test_loader_preserves_source_path_and_page_metadata_for_pdf(
    mock_pdf_loader_cls: MagicMock,
    data_dir: Path,
) -> None:
    hr = data_dir / "hr"
    hr.mkdir(parents=True, exist_ok=True)
    path = hr / "employee_handbook_2024.pdf"
    path.write_bytes(b"%PDF-1.4\n")

    mock_instance = MagicMock()
    mock_instance.load.return_value = [
        Document(page_content="Page one content", metadata={"source": "pdfminer-old"}),
        Document(
            page_content="Page two content",
            metadata={"source": "pdfminer-old", "producer": "TestProducer"},
        ),
    ]
    mock_pdf_loader_cls.return_value = mock_instance

    docs = loader_mod.load_pdf(path)

    assert len(docs) == 2
    assert docs[0].metadata["page"] == 1
    assert docs[1].metadata["page"] == 2
    assert docs[0].metadata["source"] == str(path)
    assert docs[1].metadata["source"] == str(path)
    assert docs[0].metadata["source_doc_id"] == loader_mod.make_source_doc_id(path)
    assert docs[1].metadata["source_doc_id"] == loader_mod.make_source_doc_id(path)
    assert docs[0].metadata["domain"] == "hr"
    assert docs[0].metadata["year"] == "2024"
    assert docs[0].metadata["topic"] == "employee_handbook"
    assert docs[1].metadata["producer"] == "TestProducer"
