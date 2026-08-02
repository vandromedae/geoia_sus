from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    database_url: str
    llm_provider: str
    groq_api_key: str
    groq_model: str
    ollama_url: str
    ollama_model: str
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
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 2048

# Cache TTL in seconds
CACHE_TTL = 1800  # 30 minutes
