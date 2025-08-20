from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from typing import List
from langchain_core.documents import Document
from index.faiss_store import FaissStore

class HybridRetrieverFactory:
    def __init__(self, base_docs: List[Document], store: FaissStore):
        self.base_docs = base_docs
        self.store = store

    def create(self):
        bm25 = BM25Retriever.from_documents(self.base_docs)
        bm25.k = 12
        faiss = self.store.mmr_retriever(k=12, fetch_k=60)
        return EnsembleRetriever(retrievers=[bm25, faiss], weights=[0.4, 0.6])
