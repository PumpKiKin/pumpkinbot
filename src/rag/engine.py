from typing import List
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from core.types import Answer, Source, Message
from core.config import settings
from models.llm_provider import get_llm
from rag.prompt import SYSTEM, TEMPLATE

class ChatEngine:
    def __init__(self, retriever):
        self.retriever = retriever
        self.llm = get_llm()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM),
            ("human", TEMPLATE),
        ])

    def _format_context(self, docs: List[Document]) -> str:
        parts = []
        for i, d in enumerate(docs, 1):
            title = d.metadata.get("title", "")
            url = d.metadata.get("url", "")
            snippet = d.page_content[:500].replace("\n", " ")
            parts.append(f"[{i}] {title} | {url}\n{snippet}")
        return "\n\n".join(parts)

    def _docs_to_sources(self, docs: List[Document]) -> List[Source]:
        out = []
        for d in docs:
            out.append(Source(
                title=d.metadata.get("title", ""),
                url=d.metadata.get("url", ""),
                snippet=d.page_content[:200]
            ))
        return out

    def rewrite(self, question: str, history: List[Message]) -> str:
        # 간단 재작성 (LLM 호출 최소화; 필요 시 고급 체인으로 교체)
        if not history:
            return question
        last_user = ""
        for m in reversed(history):
            if m["role"] == "user":
                last_user = m["content"]
                break
        return f"{last_user} 관련: {question}" if last_user else question

    def ask(self, question: str, history: List[Message]) -> Answer:
        q = self.rewrite(question, history)
        # 1) 후보 수집 → 2) 재정렬된 상위 n 반환
        candidates = self.retriever.invoke(q)  # List[Document] 반환
        context_str = self._format_context(candidates)

        chain_input = {
            "history": "\n".join([f"{m['role']}: {m['content']}" for m in history[-8:]]),
            "question": question,
            "context": context_str,
        }
        resp = self.prompt | self.llm
        text = (resp.invoke(chain_input)).content
        return Answer(text=text, sources=self._docs_to_sources(candidates))
