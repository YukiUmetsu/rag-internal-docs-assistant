import hashlib
from pathlib import Path
from typing import List
import re

from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader, PyPDFLoader


DATA_DIR = Path("data")


# ---------------------------
# Metadata helpers
# ---------------------------
def make_source_doc_id(path: Path) -> str:
    normalized = str(path.resolve()).lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]

def infer_metadata(path: Path):
    name = path.stem

    # refund_policy_2026 → topic=refund_policy, year=2026
    parts = name.split("_")
    year = None

    if parts[-1].isdigit():
        year = parts[-1]
        topic = "_".join(parts[:-1])
    else:
        topic = name

    return {
        "source": str(path),
        "file_name": path.name,
        "source_doc_id": make_source_doc_id(path),
        "canonical_doc_id": path.stem,
        "domain": path.parent.name,
        "file_type": path.suffix.replace(".", ""),
        "topic": topic,
        "year": year,
    }


# ---------------------------
# PDF Cleaning (IMPORTANT)
# ---------------------------
def clean_pdf_text(text: str) -> str:
    text = re.sub(r"^\s*-\s*\d+\s*-\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"Confidential.*", "", text)
    text = re.sub(r"Acme Payments.*", "", text)

    # collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------
# Loaders
# ---------------------------
def load_markdown(path: Path) -> List[Document]:
    loader = TextLoader(str(path), encoding="utf-8")
    docs = loader.load()

    for doc in docs:
        doc.metadata.update(infer_metadata(path))

    return docs


def load_pdf(path: Path) -> List[Document]:
    loader = PyPDFLoader(str(path), mode="page")
    docs = loader.load()

    for i, doc in enumerate(docs):
        doc.page_content = clean_pdf_text(doc.page_content)

        metadata = infer_metadata(path)
        metadata["page"] = i + 1

        doc.metadata.update(metadata)

    return docs


def load_all_documents() -> List[Document]:
    all_docs = []

    for path in DATA_DIR.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix == ".md":
            all_docs.extend(load_markdown(path))

        elif path.suffix == ".pdf":
            all_docs.extend(load_pdf(path))

    return all_docs