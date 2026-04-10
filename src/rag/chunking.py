from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def get_markdown_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
        separators=[
            "\n## ",
            "\n### ",
            "\n- ",
            "\n\n",
            "\n",
            " ",
            ""
        ],
    )


def get_pdf_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            ""
        ],
    )


def split_documents(documents: List[Document]) -> List[Document]:
    md_splitter = get_markdown_splitter()
    pdf_splitter = get_pdf_splitter()

    chunks = []

    for doc in documents:
        if doc.metadata["file_type"] == "pdf":
            chunks.extend(pdf_splitter.split_documents([doc]))
        else:
            chunks.extend(md_splitter.split_documents([doc]))

    return chunks