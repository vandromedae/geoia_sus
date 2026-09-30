from src.services.cache import make_key, normalizar_texto


class TestNormalizarTexto:
    def test_acento_e_caixa(self):
        assert normalizar_texto("São Paulo") == normalizar_texto("SAO PAULO")

    def test_pontuacao_final(self):
        assert normalizar_texto("Quantos médicos tem São Paulo?") == normalizar_texto(
            "quantos medicos tem sao paulo"
        )

    def test_espacos_repetidos(self):
        assert normalizar_texto("  ola   mundo  ") == normalizar_texto("ola mundo")

    def test_perguntas_diferentes_nao_colidem(self):
        assert normalizar_texto("compare São Paulo e Campinas") != normalizar_texto(
            "compare Santos e Sorocaba"
        )

    def test_vazio(self):
        assert normalizar_texto("") == ""
        assert normalizar_texto(None) == ""


class TestMakeKey:
    def test_ordem_dos_argumentos_nao_muda_a_chave(self):
        assert make_key("a", 1) != make_key("b", 1)
        assert make_key("municipios", 2, 0) == make_key("municipios", 2, 0)
