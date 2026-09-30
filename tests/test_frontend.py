import httpx
import pytest

from frontend.components.map import _coordenadas, _cor_de, _titulo, tem_pontos
from frontend.utils import _extrair_erro


class TestCoordenadas:
    def test_latitude_zero_e_valida(self):
        assert _coordenadas({"latitude": 0.0, "longitude": 10.0}) == (0.0, 10.0)

    def test_aceita_chaves_lat_lon(self):
        assert _coordenadas({"lat": -23.5, "lon": -46.6}) == (-23.5, -46.6)

    def test_ausente(self):
        assert _coordenadas({"nm_mun": "Adamantina"}) is None

    def test_lixo(self):
        assert _coordenadas({"latitude": "abc", "longitude": 1}) is None


class TestTemPontos:
    def test_lista_com_coordenadas(self):
        assert tem_pontos([{"latitude": 1.0, "longitude": 2.0}])

    def test_dicionario_de_setores(self):
        assert tem_pontos({"setores": [{"latitude": 1.0, "longitude": 2.0}]})

    def test_sem_coordenadas(self):
        assert not tem_pontos([{"nm_mun": "Adamantina"}])
        assert not tem_pontos({"setores": [{"cd_setor": "35"}]})
        assert not tem_pontos([])


class TestCorDoMarcador:
    @pytest.mark.parametrize(
        ("categoria", "cor"),
        [
            ("1. Excelente (acesso muito alto)", "green"),
            ("2. Bom (acesso alto)", "green"),
            ("3. Moderado (acesso médio)", "orange"),
            ("4. Limitado (acesso baixo)", "red"),
            ("5. Crítico (acesso muito baixo)", "red"),
            ("6. Deserto médico (sem acesso)", "red"),
        ],
    )
    def test_nivel_da_categoria(self, categoria, cor):
        assert _cor_de({"categoria_acesso": categoria}) == cor

    def test_sem_categoria_e_vermelho(self):
        assert _cor_de({}) == "red"


class TestTituloDoPopup:
    def test_municipio_e_distrito(self):
        assert _titulo({"nm_mun": "São Paulo", "nm_dist": "Itaim Bibi"}) == (
            "São Paulo — Itaim Bibi"
        )

    def test_so_municipio(self):
        assert _titulo({"nm_mun": "Campinas"}) == "Campinas"

    def test_setor_sem_nome_de_local(self):
        assert _titulo({"cd_setor": "355030801000001"}) == "355030801000001"


class TestExtrairErro:
    def test_usa_detail_da_api(self):
        resp = httpx.Response(429, json={"detail": "Limite atingido."})
        assert str(_extrair_erro(resp)) == "Limite atingido."

    def test_sem_detail(self):
        resp = httpx.Response(500, text="erro interno")
        assert "500" in str(_extrair_erro(resp))
