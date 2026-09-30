"""Loop de perguntas: roteia, roda o LLM com ferramentas e monta a resposta.

A execução das ferramentas vive em `ferramentas.py`, a projeção dos dados
para o prompt/chat/mapa em `serializacao.py` e o gate de escopo em
`roteamento.py`. Este módulo é só a coreografia entre os três.
"""

import json

import anyio
from sqlalchemy.orm import Session

from src.config import LLM_MAX_RODADAS_FERRAMENTA, LLM_MAX_TOOLS_POR_RODADA
from src.llm.base import LLMClient
from src.llm.ferramentas import executar_tool
from src.llm.prompts import SYSTEM_PROMPT
from src.llm.roteamento import MENSAGEM_FORA_DE_ESCOPO, dentro_do_escopo
from src.llm.serializacao import (
    calcular_mapa,
    mensagem_assistente,
    resposta_de_fallback,
    resumir_para_llm,
)
from src.llm.tools import ALL_TOOLS
from src.schemas import QueryResponse


async def processar_pergunta(pergunta: str, db: Session, llm: LLMClient) -> QueryResponse:
    if not dentro_do_escopo(pergunta):
        return QueryResponse(
            resposta=MENSAGEM_FORA_DE_ESCOPO,
            dados=None,
            tool_chamada=None,
        )

    # `llm.chat` e as consultas são bloqueantes; rodar no event loop serializava
    # o Uvicorn inteiro (o /health e /municipios travavam durante a chamada LLM).
    return await anyio.to_thread.run_sync(_processar_sincrono, pergunta, db, llm)


def _processar_sincrono(pergunta: str, db: Session, llm: LLMClient) -> QueryResponse:
    """Loop de ferramentas: até `LLM_MAX_RODADAS_FERRAMENTA` rodadas de chamada
    de ferramenta, e sempre uma resposta final sem ferramentas ao final.

    Antes só o primeiro `tool_call` era executado e as demais ferramentas eram
    descartadas em silêncio.
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": pergunta},
    ]
    ferramentas: list[str] = []
    dados: list[dict] | dict | None = None
    resposta_texto = ""
    houve_chamada = False

    for rodada in range(LLM_MAX_RODADAS_FERRAMENTA):
        resposta = llm.chat(messages=messages, tools=ALL_TOOLS)
        chamadas = resposta.get("tool_calls") or []
        if not chamadas:
            resposta_texto = resposta.get("content") or ""
            break

        houve_chamada = True
        chamadas = chamadas[:LLM_MAX_TOOLS_POR_RODADA]
        for indice, chamada in enumerate(chamadas):
            if not chamada.get("id"):
                chamada["id"] = f"call_{rodada}_{indice}"

        messages.append(mensagem_assistente(resposta, chamadas))

        for chamada in chamadas:
            nome = chamada["name"]
            argumentos = chamada.get("arguments") or {}
            dados = executar_tool(nome, argumentos, db)
            ferramentas.append(nome)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": chamada["id"],
                    "content": json.dumps(resumir_para_llm(dados), default=str, ensure_ascii=False),
                }
            )
    else:
        # Ainda havia tool_calls na última rodada: pede a resposta final sem tools.
        resposta_texto = llm.chat(messages=messages).get("content") or ""

    if not resposta_texto.strip():
        resposta_texto = resposta_de_fallback(ferramentas, dados, houve_chamada)
        fallback = True
    else:
        fallback = False

    dados_expostos = None if isinstance(dados, dict) and "erro" in dados else dados
    mapa_centro, mapa_zoom = calcular_mapa(dados)

    return QueryResponse(
        resposta=resposta_texto,
        dados=dados_expostos,
        tool_chamada=", ".join(ferramentas) if ferramentas else None,
        mapa_centro=mapa_centro,
        mapa_zoom=mapa_zoom,
        resposta_de_fallback=fallback,
    )
