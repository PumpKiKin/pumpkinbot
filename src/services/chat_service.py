from core.config import settings
from core.types import Answer, Message
from data.json_loader import JsonLoader
from index.faiss_store import FaissStore
from retrieval.hybrid import HybridRetrieverFactory
from retrieval.reranker import CrossEncoderWrapper
from rag.engine import ChatEngine

class ChatService:
    def __init__(self):
        self._docs = JsonLoader(settings.DATA_JSON).load()
        self._store = FaissStore()
        if not settings.index_path().exists():
            self._store.build(self._docs)
        base_retriever = HybridRetrieverFactory(self._docs, self._store).create()
        reranked = CrossEncoderWrapper(base_retriever, top_n=settings.TOP_N_RERANKED).get()
        self.engine = ChatEngine(reranked)

    def answer(self, question: str, history: list[Message]) -> Answer:
        return self.engine.ask(question, history)
