import groq
import httpx
import pytest

from src.llm.errors import LLMError
from src.llm.groq_client import _espera_da_tentativa, mapear_erro_groq
from src.llm.ollama_client import mapear_erro_ollama
from src.llm.tools import carregar_argumentos

_URL = "https://api.groq.com/openai/v1/chat/completions"


def _status_error(status: int, headers: dict | None = None) -> groq.APIStatusError:
    requisicao = httpx.Request("POST", _URL)
    resposta = httpx.Response(status, request=requisicao, headers=headers or {})
    return groq.APIStatusError(f"Error code: {status}", response=resposta, body=None)


class TestMapearErroGroq:
    def test_rate_limit_vira_429_com_retry_after(self):
        erro = mapear_erro_groq(_status_error(429, {"retry-after": "7"}))
        assert isinstance(erro, LLMError)
        assert erro.status_code == 429
        assert erro.retry_after == 7.0
        assert "limite de uso" in erro.user_message

    def test_payload_grande_vira_413(self):
        erro = mapear_erro_groq(_status_error(413))
        assert erro.status_code == 413
        assert erro.retry_after is None

    def test_erro_interno_do_provedor_vira_502(self):
        for status in (500, 502, 503, 504):
            erro = mapear_erro_groq(_status_error(status))
            assert erro.status_code == 502, status

    def test_chave_invalida_vira_401(self):
        erro = mapear_erro_groq(_status_error(401))
        assert erro.status_code == 401
        assert "GROQ_API_KEY" in erro.user_message

    def test_requisicao_invalida_vira_400(self):
        erro = mapear_erro_groq(_status_error(400))
        assert erro.status_code == 400

    def test_timeout_vira_504(self):
        requisicao = httpx.Request("POST", _URL)
        erro = mapear_erro_groq(groq.APITimeoutError(request=requisicao))
        assert erro.status_code == 504
        assert "demorou demais" in erro.user_message

    def test_falha_de_conexao_vira_502(self):
        requisicao = httpx.Request("POST", _URL)
        erro = mapear_erro_groq(groq.APIConnectionError(request=requisicao))
        assert erro.status_code == 502

    def test_excecao_desconhecida_vira_502(self):
        erro = mapear_erro_groq(RuntimeError("algo inesperado"))
        assert erro.status_code == 502

    def test_retry_after_zerado_e_ignorado(self):
        erro = mapear_erro_groq(_status_error(429, {"retry-after": "0"}))
        assert erro.retry_after is None

    def test_retry_after_nao_numerico_e_ignorado(self):
        erro = mapear_erro_groq(_status_error(429, {"retry-after": "Wed, 21 Oct"}))
        assert erro.retry_after is None


class TestBackoff:
    def test_respeita_retry_after_com_teto(self):
        assert _espera_da_tentativa(0, 120.0, 429) == 20.0
        assert _espera_da_tentativa(0, 2.0, 429) == 2.0

    def test_backoff_exponencial_com_teto(self):
        assert _espera_da_tentativa(0, None, 502) == 1.0
        assert _espera_da_tentativa(1, None, 502) == 2.0
        assert _espera_da_tentativa(10, None, 502) == 20.0

    def test_429_espera_mais_por_ser_janela_de_60s(self):
        assert _espera_da_tentativa(0, None, 429) == 10.0
        assert _espera_da_tentativa(1, None, 429) == 20.0
        assert _espera_da_tentativa(5, None, 429) == 20.0


class TestMapearErroOllama:
    def test_modelo_inexistente(self):
        requisicao = httpx.Request("POST", "http://ollama/api/chat")
        exc = httpx.HTTPStatusError(
            "404", request=requisicao, response=httpx.Response(404, request=requisicao)
        )
        erro = mapear_erro_ollama(exc)
        assert erro.status_code == 502
        assert "ollama pull" in erro.user_message

    def test_429_vira_429(self):
        requisicao = httpx.Request("POST", "http://ollama/api/chat")
        exc = httpx.HTTPStatusError(
            "429", request=requisicao, response=httpx.Response(429, request=requisicao)
        )
        assert mapear_erro_ollama(exc).status_code == 429

    def test_timeout_vira_504(self):
        assert mapear_erro_ollama(httpx.ConnectTimeout("x")).status_code == 504

    def test_conexao_vira_502(self):
        assert mapear_erro_ollama(httpx.ConnectError("x")).status_code == 502


class TestCarregarArgumentos:
    def test_dict_retorna_o_proprio_dict(self):
        assert carregar_argumentos({"a": 1}) == {"a": 1}

    def test_string_vazia_retorna_dict_vazio(self):
        assert carregar_argumentos("") == {}

    def test_none_retorna_dict_vazio(self):
        assert carregar_argumentos(None) == {}

    def test_json_malformado_retorna_dict_vazio(self):
        assert carregar_argumentos('{"municipio": "Camp') == {}

    def test_json_nao_dict_retorna_dict_vazio(self):
        assert carregar_argumentos("[1, 2, 3]") == {}

    def test_json_valido_e_carregado(self):
        assert carregar_argumentos('{"limite": 5}') == {"limite": 5}


@pytest.mark.parametrize("valor", [{"a": 1}, "", None, "{", "[]"])
def test_carregar_argumentos_nunca_lanca(valor):
    assert isinstance(carregar_argumentos(valor), dict)
