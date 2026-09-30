import os

# Must be set before any src import that triggers Settings()
os.environ.setdefault("DATABASE_URL", "postgresql://geoai:geoai_secret@localhost:5432/geoia_sus")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("GROQ_MODEL", "test")
os.environ.setdefault("OLLAMA_URL", "http://ollama:11434")
os.environ.setdefault("OLLAMA_MODEL", "test")

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.fake_client import FakeLLMClient


@pytest.fixture(autouse=True)
def _cache_vazio():
    """Cache in-process vaza entre testes (mesma chave de pergunta)."""
    from src.services.cache import cache_clear

    cache_clear()
    yield
    cache_clear()


@pytest.fixture(scope="session")
def banco_disponivel() -> bool:
    """Tem PostGIS no ar? Fica em cache na sessão inteira."""
    try:
        from sqlalchemy import text

        from src.database import engine

        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
def exige_banco(banco_disponivel):
    """Pule o teste quando não há banco — `make test` roda sem o Docker.

    Os testes que dependem de PostGIS pedem esta fixture (diretamente ou
    através de `db_session`); os demais rodam em qualquer ambiente.
    """
    if not banco_disponivel:
        pytest.skip("PostGIS indisponível — `make up` antes de `make test`")


@pytest.fixture
def fake_llm():
    return FakeLLMClient(content="Resposta de teste.")


@pytest.fixture
def fake_llm_with_tool():
    return FakeLLMClient(
        tool_call={
            "name": "ranking_municipios",
            "arguments": {"indicador": "medicos_por_1k", "ordem": "asc", "limite": 5},
        }
    )


@pytest.fixture
def db_session(exige_banco):
    from sqlalchemy.orm import sessionmaker

    from src.database import engine

    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient

    from src.api.main import app

    return TestClient(app)
