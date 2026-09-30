import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_llm_client
from src.api.main import app
from src.llm.errors import LLMError
from src.llm.fake_client import FakeLLMClient


@pytest.fixture
def fake_llm():
    return FakeLLMClient(content="Resposta simulada do LLM.")


@pytest.fixture
def client(fake_llm):
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


class TestHealth:
    def test_health_endpoint(self, client, exige_banco):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert data["database"] == "connected"


class TestMunicipios:
    def test_listar_municipios(self, client, exige_banco):
        resp = client.get("/municipios/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_municipio_structure(self, client, exige_banco):
        resp = client.get("/municipios/")
        data = resp.json()
        mun = data[0]
        assert "cod_mun_ibge" in mun
        assert "nm_mun" in mun
        assert "populacao" in mun

    def test_buscar_municipio_existente(self, client, exige_banco):
        resp = client.get("/municipios/3500105")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cod_mun_ibge"] == "3500105"
        assert data["nm_mun"] == "Adamantina"

    def test_buscar_municipio_inexistente(self, client, exige_banco):
        resp = client.get("/municipios/999999")
        assert resp.status_code == 404


class TestQuery:
    def test_query_simples(self, client):
        # Precisa passar pelo gate de escopo ("Olá" era recusado antes do LLM).
        resp = client.post("/query", json={"pergunta": "Quantos médicos tem Adamantina?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "resposta" in data

    def test_query_estrutura(self, client):
        resp = client.post("/query", json={"pergunta": "Liste os municípios com menos médicos"})
        data = resp.json()
        assert "resposta" in data
        assert "dados" in data
        assert "tool_chamada" in data


class _LLMQueFalha:
    def __init__(self, erro):
        self.erro = erro

    def chat(self, messages, tools=None):
        raise self.erro


class TestErrosDoLLM:
    """429/413/504 precisam chegar como tal — antes tudo virava 500."""

    @pytest.fixture
    def client_com_falha(self, client):
        def _instalar(erro):
            app.dependency_overrides[get_llm_client] = lambda: _LLMQueFalha(erro)

        return _instalar

    def test_rate_limit_vira_429_com_retry_after(self, client, client_com_falha):
        client_com_falha(LLMError("Limite atingido.", status_code=429, retry_after=12))
        resp = client.post("/query", json={"pergunta": "quantos médicos tem São Paulo"})
        assert resp.status_code == 429
        assert resp.json() == {"detail": "Limite atingido."}
        assert resp.headers["retry-after"] == "12"

    def test_payload_grande_vira_413(self, client, client_com_falha):
        client_com_falha(LLMError("Consulta muito grande para o modelo.", status_code=413))
        resp = client.post("/query", json={"pergunta": "quantos médicos tem São Paulo"})
        assert resp.status_code == 413
        assert "Consulta muito grande" in resp.json()["detail"]

    def test_timeout_vira_504(self, client, client_com_falha):
        client_com_falha(LLMError("Demorou demais.", status_code=504))
        resp = client.post("/query", json={"pergunta": "quantos médicos tem São Paulo"})
        assert resp.status_code == 504

    def test_erro_de_ferramenta_nao_vira_500(self, client, client_com_falha):
        client_com_falha(LLMError("Tool desconhecida: x", status_code=502))
        resp = client.post("/query", json={"pergunta": "quantos médicos tem São Paulo"})
        assert resp.status_code == 502
        assert "500" not in resp.text


class _LLMContador:
    def __init__(self, conteudo="Resposta simulada do LLM."):
        self.chamadas = 0
        self.conteudo = conteudo

    def chat(self, messages, tools=None):
        self.chamadas += 1
        return {"content": self.conteudo}


class TestHealthSemBanco:
    def test_health_503_quando_banco_fora(self, client, monkeypatch):
        from src.api.routes import health as modulo_health

        class _MotorQuebrado:
            def connect(self):
                raise RuntimeError("banco fora")

        monkeypatch.setattr(modulo_health, "engine", _MotorQuebrado())

        resp = client.get("/health")

        assert resp.status_code == 503
        assert resp.json() == {"status": "error", "database": "unavailable"}


class TestMunicipiosPaginacaoECache:
    def test_paginacao_retorna_blocos_distintos(self, client, exige_banco):
        primeiro = client.get("/municipios/?limite=3&offset=0").json()
        segundo = client.get("/municipios/?limite=3&offset=3").json()

        assert len(primeiro) == 3
        assert len(segundo) == 3
        assert {m["cod_mun_ibge"] for m in primeiro}.isdisjoint(
            {m["cod_mun_ibge"] for m in segundo}
        )

    def test_limite_invalido_e_rejeitado(self, client):
        assert client.get("/municipios/?limite=0").status_code == 422
        assert client.get("/municipios/?offset=-1").status_code == 422

    def test_segunda_chamada_vem_do_cache(self, client, exige_banco):
        from src.services.cache import cache_get, make_key

        client.get("/municipios/?limite=2&offset=0")
        assert cache_get(make_key("municipios", 2, 0)) is not None
        assert cache_get(make_key("municipios", 2, 50)) is None

    def test_unico_municipio_entra_no_cache(self, client, exige_banco):
        from src.services.cache import cache_get, make_key

        client.get("/municipios/3500105")
        assert cache_get(make_key("municipio", "3500105")) is not None


class TestCacheDaPergunta:
    def test_pergunta_repetida_nao_chama_o_llm_de_novo(self, client):
        contador = _LLMContador()
        app.dependency_overrides[get_llm_client] = lambda: contador

        primeira = client.post("/query", json={"pergunta": "Quantos médicos tem São Paulo?"})
        segunda = client.post("/query", json={"pergunta": "quantos medicos tem sao paulo?"})

        assert contador.chamadas == 1
        assert primeira.json()["resposta"] == segunda.json()["resposta"]

    def test_resposta_de_fallback_nao_entra_no_cache(self, client):
        contador = _LLMContador(conteudo="")
        app.dependency_overrides[get_llm_client] = lambda: contador
        pergunta = "quantos médicos tem Campinas?"

        resp = client.post("/query", json={"pergunta": pergunta})

        assert resp.json()["resposta_de_fallback"] is True
        from src.services.cache import cache_get, make_key, normalizar_texto

        assert cache_get(make_key("query", normalizar_texto(pergunta))) is None
