from langchain_google_genai import ChatGoogleGenerativeAI
from core.config import settings
import os
from dotenv import load_dotenv

load_dotenv()

def get_llm():
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY 또는 GEMINI_API_KEY가 없습니다 (.env 확인).")
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        temperature=settings.TEMPERATURE,
        google_api_key=key,   # ← 키를 명시적으로 전달
        convert_system_message_to_human=True,
    )
