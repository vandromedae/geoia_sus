import json
import threading
import time
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
