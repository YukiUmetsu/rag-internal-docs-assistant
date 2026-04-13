class FakeVectorStore:
    def __init__(self, docs):
        self.docs = docs
        self.calls = []

    def similarity_search(self, query, k=4, filter=None, fetch_k=20):
        call = {"query": query, "k": k}
        if filter is not None:
            call["filter"] = filter
            call["fetch_k"] = fetch_k
        self.calls.append(call)

        filtered = [
            doc
            for doc in self.docs
            if query.lower() in doc.page_content.lower()
        ]
        if filter is not None:
            filtered = [
                doc
                for doc in (filtered or self.docs)
                if all(str(doc.metadata.get(key)) == str(value) for key, value in filter.items())
            ]
            return filtered[:k]

        return (filtered or self.docs)[:k]

    def save_local(self, path):
        self.calls.append({"path": path})

    def load_local(self, path):
        self.calls.append({"path": path})
        return self.docs

    def as_retriever(self):
        return self
