from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document


def save_chunks(docs: Iterable[Document], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for doc in docs:
            record = {
                "page_content": doc.page_content,
                "metadata": doc.metadata,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_chunks(path: str | Path) -> list[Document]:
    input_path = Path(path)
    docs: list[Document] = []

    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            docs.append(
                Document(
                    page_content=record["page_content"],
                    metadata=record["metadata"],
                )
            )

    return docs