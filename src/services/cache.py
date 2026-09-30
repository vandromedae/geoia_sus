import json
import threading
import time
import unicodedata
from typing import Any

from src.config import CACHE_TTL

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def cache_get(key: str) -> Any | None:
    with _lock:
        if key in _cache:
            ts, value = _cache[key]
            if time.time() - ts < CACHE_TTL:
                return value
            del _cache[key]
    return None


def cache_set(key: str, value: Any):
    with _lock:
        _cache[key] = (time.time(), value)


def cache_clear():
    with _lock:
        _cache.clear()


def make_key(*args) -> str:
    return json.dumps(args, sort_keys=True, default=str)


def normalizar_texto(texto: str) -> str:
    """Chave de cache insensível a acento, caixa, pontuação e espaços.

    "Quantos médicos tem São Paulo?" e "quantos medicos tem Sao paulo" são a
    mesma pergunta para o modelo — e cada chamada custa cotas do tier free do
    Groq.
    """
    sem_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c)
    )
    so_palavras = "".join(c if c.isalnum() or c.isspace() else " " for c in sem_acentos)
    return " ".join(so_palavras.casefold().split())
