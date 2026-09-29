import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")


def _extrair_erro(resp: httpx.Response) -> RuntimeError:
    """Transforma `429 Client Error` em algo que o usuário entende.

    A API devolve `{"detail": "..."}` para 429/413/502/504; sem isto o usuário
    via apenas "429 Client Error ... ".
    """
    try:
        detail = resp.json().get("detail")
    except ValueError:
        detail = None
    if not detail:
        detail = f"API respondeu {resp.status_code} {resp.reason_phrase}."
    return RuntimeError(detail)


def query_api(pergunta: str) -> dict:
    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{API_URL}/query", json={"pergunta": pergunta})
        if resp.status_code >= 400:
            raise _extrair_erro(resp)
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
