"""Erro de domínio do LLM.

O orquestrador NÃO deve vazar exceções do provedor (groq.* / httpx.*) para cima:
elas terminariam num 500 genérico. Cada provedor converte seu erro aqui e o
FastAPI (handler em `src/api/main.py`) devolve o `status_code` correspondente —
429 (limite), 413 (payload grande), 504 (timeout) ou 502 (provedor indisponível).
"""

from __future__ import annotations


class LLMError(Exception):
    """Falha do provedor de LLM já traduzida para o usuário."""

    def __init__(
        self,
        user_message: str,
        *,
        status_code: int = 502,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code
        self.retry_after = retry_after
