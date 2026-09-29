import httpx

from src.config import LLM_MAX_TOKENS, LLM_TEMPERATURE
from src.llm.errors import LLMError
from src.llm.tools import carregar_argumentos


def mapear_erro_ollama(exc: Exception) -> LLMError:
    """Converte erro do httpx/Ollama em `LLMError` com status HTTP adequado."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 404:
            return LLMError(
                "Modelo não encontrado no Ollama. Rode `ollama pull "
                "qwen3:8b` ou ajuste OLLAMA_MODEL no .env.",
                status_code=502,
            )
        if status == 429:
            return LLMError(
                "O Ollama está sobrecarregado. Tente novamente em instantes.",
                status_code=429,
            )
        if status < 500:
            return LLMError(
                "O Ollama recusou a requisição.",
                status_code=400,
            )
        return LLMError(
            "O Ollama retornou um erro inesperado.",
            status_code=502,
        )

    if isinstance(exc, httpx.TimeoutException):
        return LLMError(
            "O modelo demorou demais para responder. Tente novamente.",
            status_code=504,
        )

    if isinstance(exc, httpx.HTTPError):
        return LLMError(
            "Não foi possível conectar ao Ollama.",
            status_code=502,
        )

    return LLMError("Erro inesperado ao falar com o Ollama.", status_code=502)


class OllamaClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._sequencia = 0

    def _novo_id(self) -> str:
        # Ids precisam ser únicos na conversa: um loop de ferramentas reutiliza
        # `call_0` em várias rodadas e o provedor recusa (ou confunde) o histórico.
        self._sequencia += 1
        return f"call_{self._sequencia}"

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": LLM_TEMPERATURE,
                "num_predict": LLM_MAX_TOKENS,
            },
        }
        if tools:
            payload["tools"] = tools

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise mapear_erro_ollama(exc) from exc
        except ValueError as exc:  # corpo da resposta não é JSON
            raise LLMError(
                "O Ollama devolveu uma resposta inválida.",
                status_code=502,
            ) from exc

        msg = data.get("message") or {}

        result = {"content": msg.get("content") or "", "tool_calls": []}
        if msg.get("tool_calls"):
            result["tool_calls"] = [
                {
                    "id": self._novo_id(),
                    "name": tc["function"]["name"],
                    "arguments": carregar_argumentos(tc["function"]["arguments"]),
                }
                for tc in msg["tool_calls"]
            ]
        return result
