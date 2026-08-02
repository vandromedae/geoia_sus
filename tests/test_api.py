import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_llm_client
from src.api.main import app
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
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert data["database"] == "connected"


class TestMunicipios:
    def test_listar_municipios(self, client):
        resp = client.get("/municipios/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_municipio_structure(self, client):
        resp = client.get("/municipios/")
        data = resp.json()
        mun = data[0]
        assert "cod_mun_ibge" in mun
        assert "nm_mun" in mun
        assert "populacao" in mun

    def test_buscar_municipio_existente(self, client):
        resp = client.get("/municipios/350010")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cod_mun_ibge"] == "350010"
        assert data["nm_mun"] == "Adamantina"

    def test_buscar_municipio_inexistente(self, client):
        resp = client.get("/municipios/999999")
        assert resp.status_code == 404


class TestQuery:
    def test_query_simples(self, client):
        resp = client.post("/query", json={"pergunta": "Olá"})
        assert resp.status_code == 200
        data = resp.json()
        assert "resposta" in data

    def test_query_estrutura(self, client):
        resp = client.post("/query", json={"pergunta": "teste"})
        data = resp.json()
        assert "resposta" in data
        assert "dados" in data
        assert "tool_chamada" in data
