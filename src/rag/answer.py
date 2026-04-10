from __future__ import annotations
from langchain_core.documents.base import Document

import argparse
from typing import List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from src.rag.llm import get_llm
from src.rag.retrieve import retrieve


def format_context(docs: List[Document]) -> str:
    parts: List[str] = []

    for i, doc in enumerate[Document](docs, start=1):
        source = doc.metadata.get("file_name", "unknown")
        domain = doc.metadata.get("domain", "unknown")
        year = doc.metadata.get("year", "unknown")
        page = doc.metadata.get("page")

        header = f"[Document {i}] source={source}, domain={domain}, year={year}"
        if page is not None:
            header += f", page={page}"

        parts.append(f"{header}\n{doc.page_content}")

    return "\n\n".join(parts)


def build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are an internal company assistant. "
                    "Answer only using the retrieved context. "
                    "If the context is insufficient or conflicting, say so clearly. "
                    "Prefer newer policy versions when both old and new policies appear. "
                    "Be concise and cite the document numbers you used."
                ),
            ),
            (
                "human",
                (
                    "Question:\n{question}\n\n"
                    "Retrieved context:\n{context}\n\n"
                    "Answer the question using only the retrieved context."
                ),
            ),
        ]
    )


def answer_question(question: str, k: int = 8) -> tuple[str, List[Document]]:
    docs = retrieve(query=question, k=k)
    context = format_context(docs)

    prompt = build_prompt()
    llm = get_llm()

    chain = prompt | llm
    response = chain.invoke(
        {
            "question": question,
            "context": context,
        }
    )

    return response.content, docs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Answer a question using retrieved context.")

    parser.add_argument(
        "--query",
        required=True,
        help="Question to answer.",
    )

    parser.add_argument(
        "--k",
        type=int,
        default=8,
        help="Number of raw retrieval results before cleanup.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    answer, docs = answer_question(
        question=args.query,
        k=args.k,
    )

    print("\nAnswer:\n")
    print(answer)

    print("\nSources:\n")
    for i, doc in enumerate(docs, start=1):
        print(f"[Document {i}] {doc.metadata}")


if __name__ == "__main__":
    main()