class FakeVectorStore:
    def __init__(self, docs):
        self.docs = docs
        self.calls = []

    def similarity_search(self, query, k=4):
        self.calls.append({"query": query, "k": k})

        filtered = [
            doc
            for doc in self.docs
            if query.lower() in doc.page_content.lower()
        ]

        return (filtered or self.docs)[:k]

    def save_local(self, path):
        self.calls.append({"path": path})

    def load_local(self, path):
        self.calls.append({"path": path})
        return self.docs

    def as_retriever(self):
        return self
