from collections.abc import Generator

from fastapi import HTTPException
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
    if settings.llm_provider == "fake":
        from src.llm.fake_client import FakeLLMClient

        return FakeLLMClient(content="Resposta simulada (LLM_PROVIDER=fake).")

    if settings.llm_provider == "ollama":
        from src.llm.ollama_client import OllamaClient

        return OllamaClient(
            base_url=settings.ollama_url,
            model=settings.ollama_model,
        )

    if not settings.groq_api_key.strip():
        raise HTTPException(
            status_code=503,
            detail=(
                "LLM_PROVIDER=groq, mas GROQ_API_KEY não está configurada. "
                "Obtenha uma chave em https://console.groq.com/keys e defina-a no .env."
            ),
        )

    from src.llm.groq_client import GroqClient

    return GroqClient(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
    )
