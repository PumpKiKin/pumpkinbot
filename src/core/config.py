from dataclasses import dataclass
from pathlib import Path

@dataclass
class Settings:
    APP_TITLE: str = "로욜라도서관 FAQ 챗봇"
    DATA_JSON: str = "database/detail_data.json"
    INDEX_DIR: str = "faiss_index"

    # Embeddings
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-base"  # 또는 "BAAI/bge-m3"

    # Retrieval
    TOP_K_CANDIDATES: int = 20
    TOP_N_RERANKED: int = 4

    # LLM
    LLM_MODEL: str = "gemini-1.5-flash"
    TEMPERATURE: float = 0.2

    # Chunking
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100

    def index_path(self) -> Path:
        return Path(self.INDEX_DIR)

settings = Settings()
