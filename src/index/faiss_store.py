from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List
from langchain_core.documents import Document
from core.config import settings

class FaissStore:
    def __init__(self):
        self.emb = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
        self.vs: FAISS | None = None

    def build(self, docs: List[Document]):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        chunks = splitter.split_documents(docs)
        self.vs = FAISS.from_documents(chunks, embedding=self.emb)
        self.vs.save_local(settings.INDEX_DIR)

    def load(self) -> FAISS:
        if self.vs:
            return self.vs
        self.vs = FAISS.load_local(settings.INDEX_DIR, self.emb, allow_dangerous_deserialization=True)
        return self.vs

    def mmr_retriever(self, k: int = 8, fetch_k: int = 30):
        store = self.load()
        return store.as_retriever(search_type="mmr", search_kwargs={"k": k, "fetch_k": fetch_k, "lambda_mult": 0.5})
