from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

# Modelos confirmados como disponíveis no Groq (tier free).
GROQ_MODEL_PADRAO = "qwen/qwen3.8-27b"


class Settings(BaseSettings):
    # extra="ignore": o .env é compartilhado com o docker-compose e contém chaves
    # que a aplicação não usa (POSTGRES_PASSWORD, POSTGRES_DB, ...).
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    database_url: str = "postgresql://geoai:geoai_secret@localhost:5432/geoia_sus"
    llm_provider: Literal["groq", "ollama", "fake"] = "groq"
    groq_api_key: str = ""
    groq_model: str = GROQ_MODEL_PADRAO
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    cors_origins: list[str] = ["http://localhost:8501"]


settings = Settings()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"

# Data release (GitHub Releases)
DATA_RELEASE_URL = "https://github.com/vandromedae/geoia_sus/releases/latest/download"

# Parquet files
PARQUET_SETORES = DATA_DIR / "setores_com_acessibilidade_real.parquet"
PARQUET_MUNICIPIOS = DATA_DIR / "base_municipal_densidade_medica.parquet"
PARQUET_CNES = DATA_DIR / "cnes_agregados.parquet"

# Data release assets
RELEASE_ASSETS = {
    "setores": "setores_com_acessibilidade_real.parquet",
    "municipios": "base_municipal_densidade_medica.parquet",
    "cnes": "cnes_agregados.parquet",
}

# LLM defaults
# LLM_TEMPERATURE: 0.1 = baixa variância para resposta factual.
# LLM_MAX_TOKENS: o tier free do Groq limita a SAÍDA a 1000 tokens/min (OTPM).
# Com 2048 o primeiro request já estourava: "429 ... OTPM Limit 1000, Requested 1420".
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 800

# Entrada (ITPM) do tier free é de 7000 tokens/min — ver LLM_AMOSTRA_LLM.
LLM_MAX_RODADAS_FERRAMENTA = 2
LLM_MAX_TOOLS_POR_RODADA = 3
LLM_MAX_TENTATIVAS = 3
# 429 do Groq é janela de 60 s (OTPM): backoff de 1 s/2 s não adianta nada.
LLM_ESPERA_429 = 10.0
# Teto por espera: o frontend dá timeout em 60 s (10 + 20 + chamadas < 60).
LLM_TENTATIVAS_ESPERA_MAX = 20.0

# Quantidade de itens de uma LISTA enviada ao LLM (a lista crua vai ao frontend).
LLM_AMOSTRA_LLM = 20
# Limite superior do parâmetro `limite` das ferramentas (o frontend renderiza tudo).
LIMITE_MAXIMO_LISTA = 100

# Cache TTL in seconds
CACHE_TTL = 1800  # 30 minutes
