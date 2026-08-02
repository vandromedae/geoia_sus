import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")


def query_api(pergunta: str) -> dict:
    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{API_URL}/query", json={"pergunta": pergunta})
        resp.raise_for_status()
        return resp.json()


def get_municipios() -> list[dict]:
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{API_URL}/municipios/")
        resp.raise_for_status()
        return resp.json()


def health_check() -> dict:
    with httpx.Client(timeout=5) as client:
        resp = client.get(f"{API_URL}/health")
        resp.raise_for_status()
        return resp.json()
