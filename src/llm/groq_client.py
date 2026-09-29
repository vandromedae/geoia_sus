import time

import groq
from groq import Groq

from src.config import (
    LLM_ESPERA_429,
    LLM_MAX_TENTATIVAS,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TENTATIVAS_ESPERA_MAX,
)
from src.llm.errors import LLMError
from src.llm.tools import carregar_argumentos

# Status que valem a pena tentar de novo: limites de janela e instabilidade do provedor.
_STATUS_RECUPERAVEIS = {429, 500, 502, 503, 504}


def _ler_retry_after(exc: Exception) -> float | None:
    """Lê o cabeçalho `Retry-After` (em segundos) quando o provedor envia."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    valor = headers.get("retry-after")
    if valor is None:
        return None
    try:
        segundos = float(valor)
    except (TypeError, ValueError):
        return None
    return segundos if segundos > 0 else None


def mapear_erro_groq(exc: Exception) -> LLMError:
    """Converte exceção do SDK do Groq em `LLMError` com status HTTP adequado.

    Sem isso tudo virava 500 — o usuário via apenas "Internal Server Error"
    mesmo quando era limite de uso (429) ou payload grande (413). A decisão é
    tomada pelo código HTTP: o SDK nem sempre levanta a subclasse esperada
    (`RateLimitError`), mas o `status_code` está sempre lá.
    """
    retry_after = _ler_retry_after(exc)

    if isinstance(exc, groq.APITimeoutError):
        return LLMError(
            "O modelo demorou demais para responder. Tente novamente.",
            status_code=504,
        )

    if isinstance(exc, groq.APIConnectionError):
        return LLMError(
            "Não foi possível conectar ao serviço de IA. Tente novamente.",
            status_code=502,
        )

    if isinstance(exc, groq.APIStatusError):
        status = exc.status_code
        if status == 401:
            return LLMError(
                "Chave de API do Groq inválida ou ausente. Configure GROQ_API_KEY no .env.",
                status_code=401,
            )
        if status == 429:
            return LLMError(
                "O serviço de IA atingiu o limite de uso no momento. "
                "Tente novamente em alguns instantes.",
                status_code=429,
                retry_after=retry_after,
            )
        if status == 413:
            return LLMError(
                "A consulta enviada ao modelo excede o limite de tokens de entrada. "
                "Reformule a pergunta de forma mais direta.",
                status_code=413,
            )
        if status in (400, 422):
            return LLMError(
                "O serviço de IA recusou a requisição.",
                status_code=400,
            )
        if status >= 500:
            return LLMError(
                "O serviço de IA está instável no momento. Tente novamente.",
                status_code=502,
                retry_after=retry_after,
            )
        return LLMError(
            "O serviço de IA retornou um erro inesperado.",
            status_code=502,
            retry_after=retry_after,
        )

    if isinstance(exc, groq.GroqError):
        return LLMError(
            "Erro no cliente do Groq. Tente novamente.",
            status_code=502,
        )

    return LLMError(
        "Erro inesperado ao falar com o serviço de IA.",
        status_code=502,
    )


def _espera_da_tentativa(
    tentativa: int, retry_after: float | None, status_code: int | None
) -> float:
    """Backoff exponencial, ancorado no `Retry-After` e com teto curto.

    O teto importa: o timeout do frontend é de 60 s e o `Retry-After` do Groq
    pode indicar janelas longas para OTPM.
    """
    if retry_after is not None:
        return min(retry_after, LLM_TENTATIVAS_ESPERA_MAX)
    if status_code == 429:
        return min(LLM_ESPERA_429 * (tentativa + 1), LLM_TENTATIVAS_ESPERA_MAX)
    return min(2.0**tentativa, LLM_TENTATIVAS_ESPERA_MAX)


class GroqClient:
    def __init__(self, api_key: str, model: str, max_tentativas: int = LLM_MAX_TENTATIVAS):
        # max_retries=0: a política de retry é desta classe (o SDK faria retries
        # paralelos ao nosso e multiplicaria chamadas no rate limit).
        self.client = Groq(api_key=api_key, max_retries=0)
        self.model = model
        self.max_tentativas = max(1, max_tentativas)

    def _montar_kwargs(self, messages: list[dict], tools: list[dict] | None) -> dict:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return kwargs

    def _traduzir_resposta(self, response) -> dict:
        msg = response.choices[0].message
        result = {"content": msg.content or "", "tool_calls": []}
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": carregar_argumentos(tc.function.arguments),
                }
                for tc in msg.tool_calls
            ]
        return result

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        kwargs = self._montar_kwargs(messages, tools)

        for tentativa in range(self.max_tentativas):
            try:
                response = self.client.chat.completions.create(**kwargs)
                return self._traduzir_resposta(response)
            except (
                groq.RateLimitError,
                groq.APITimeoutError,
                groq.APIConnectionError,
                groq.APIStatusError,
            ) as exc:
                erro = mapear_erro_groq(exc)
                ultima = tentativa == self.max_tentativas - 1
                if ultima or erro.status_code not in _STATUS_RECUPERAVEIS:
                    raise erro from exc
                time.sleep(_espera_da_tentativa(tentativa, erro.retry_after, erro.status_code))

        raise LLMError("Erro inesperado ao falar com o Groq.", status_code=502)
