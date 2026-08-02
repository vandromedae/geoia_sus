from collections.abc import Generator

from sqlalchemy.orm import Session

from src.config import settings
from src.database import SessionLocal
from src.llm.base import LLMClient


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "ollama":
        from src.llm.ollama_client import OllamaClient

        return OllamaClient(
            base_url=settings.ollama_url,
            model=settings.ollama_model,
        )
    from src.llm.groq_client import GroqClient

    return GroqClient(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
    )
