from langchain_core.documents import Document


def make_doc(content, source="test.md", **metadata):
    return Document(
        page_content=content,
        metadata={"source": source, **metadata},
    )