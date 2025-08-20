import json
from typing import List
from langchain_core.documents import Document
from core.text_utils import normalize

class JsonLoader:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> List[Document]:
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        docs = []
        for item in data:
            content = item.get("description", "")
            if isinstance(content, list):
                content = "\n".join(
                    [c if isinstance(c, str) else json.dumps(c, ensure_ascii=False) for c in content]
                )
            elif isinstance(content, dict):
                content = "\n".join(f"{k}: {v}" for k, v in content.items())

            meta = {
                "category": item.get("category", ""),
                "subcategory": item.get("subcategory", ""),
                "title": item.get("title", ""),
                "url": item.get("url", ""),
            }
            combined = f"[제목] {meta['title']}\n[분류] {meta['category']}>{meta['subcategory']}\n\n{normalize(content)}"
            docs.append(Document(page_content=combined, metadata=meta))
        return docs
