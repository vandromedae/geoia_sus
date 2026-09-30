import os

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000")

# `/query` faz até `LLM_MAX_RODADAS_FERRAMENTA` rodadas de ferramenta mais a
# resposta final — no tier free do Groq isso chega a ~45 s. Com um único
# `timeout=60` a conexão morria exatamente na consulta mais demorada.
TEMPO_LEITURA = float(os.getenv("API_TIMEOUT_LEITURA", "120"))
TIMEOUT = httpx.Timeout(connect=5.0, read=TEMPO_LEITURA, write=10.0, pool=5.0)


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
    with httpx.Client(timeout=TIMEOUT) as client:
        try:
            resp = client.post(f"{API_URL}/query", json={"pergunta": pergunta})
        except httpx.TimeoutException as erro:
            raise RuntimeError(
                f"A consulta não terminou em {TEMPO_LEITURA:.0f}s. "
                "Tente de novo ou faça uma pergunta mais direta."
            ) from erro
        except httpx.HTTPError as erro:
            raise RuntimeError(f"Sem conexão com a API em {API_URL}: {erro}") from erro
        if resp.status_code >= 400:
            raise _extrair_erro(resp)
        return resp.json()


def health_check() -> dict:
    with httpx.Client(timeout=5) as client:
        resp = client.get(f"{API_URL}/health")
        if resp.status_code >= 400:
            raise _extrair_erro(resp)
        return resp.json()
