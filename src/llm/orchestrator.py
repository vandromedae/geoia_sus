import json

import anyio
from sqlalchemy.orm import Session

from src.config import (
    LIMITE_MAXIMO_LISTA,
    LLM_AMOSTRA_LLM,
    LLM_MAX_RODADAS_FERRAMENTA,
    LLM_MAX_TOOLS_POR_RODADA,
)
from src.llm.base import LLMClient
from src.llm.prompts import SYSTEM_PROMPT
from src.llm.tools import ALL_TOOLS
from src.schemas import QueryResponse
from src.services.spatial import (
    buscar_setores_municipio_db,
    buscar_setores_proximos_db,
    comparar_municipios_db,
    ranking_municipios_db,
    resumo_setores_db,
)

SCOPE_KEYWORDS = [
    "saúde",
    "saude",
    "médico",
    "medico",
    "médicos",
    "medicos",
    "hospital",
    "ubs",
    "posto de saúde",
    "posto de saude",
    "atenção primaria",
    "atencao primaria",
    "acesso",
    "e2sfca",
    "densidade",
    "população",
    "populacao",
    "setor",
    "município",
    "municipio",
    "campinas",
    "santos",
    "são paulo",
    "sao paulo",
    "guarulhos",
    "sorocaba",
    "ranking",
    "comparar",
    "comparação",
    "comparacao",
    "compare",
    "cnes",
    "leito",
    "leitos",
    "enfermeiro",
    "enfermeiros",
    "dentista",
    "farmácia",
    "farmacia",
    "mostre",
    "exiba",
    "liste",
]


def _checar_escopo(pergunta: str) -> bool:
    pergunta_lower = pergunta.lower()
    return any(kw in pergunta_lower for kw in SCOPE_KEYWORDS)


async def processar_pergunta(pergunta: str, db: Session, llm: LLMClient) -> QueryResponse:
    if not _checar_escopo(pergunta):
        return QueryResponse(
            resposta="Essa pergunta está fora do escopo do GeoIA_SUS. "
            "Posso ajudar com perguntas sobre acesso à saúde, densidade "
            "de médicos, e dados do SUS no Estado de São Paulo.",
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

        messages.append(_mensagem_assistente(resposta, chamadas))

        for chamada in chamadas:
            nome = chamada["name"]
            argumentos = chamada.get("arguments") or {}
            dados = _executar_tool(nome, argumentos, db)
            ferramentas.append(nome)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": chamada["id"],
                    "content": json.dumps(
                        _resumir_para_llm(dados), default=str, ensure_ascii=False
                    ),
                }
            )
    else:
        # Ainda havia tool_calls na última rodada: pede a resposta final sem tools.
        resposta_texto = llm.chat(messages=messages).get("content") or ""

    if not resposta_texto.strip():
        resposta_texto = _resposta_de_fallback(ferramentas, dados, houve_chamada)

    dados_expostos = None if isinstance(dados, dict) and "erro" in dados else dados
    mapa_centro, mapa_zoom = _calcular_mapa(dados)

    return QueryResponse(
        resposta=resposta_texto,
        dados=dados_expostos,
        tool_chamada=", ".join(ferramentas) if ferramentas else None,
        mapa_centro=mapa_centro,
        mapa_zoom=mapa_zoom,
    )


def _calcular_mapa(dados) -> tuple[list[float] | None, int]:
    """Centra o mapa no primeiro ponto georreferenciado do resultado."""
    pontos = dados.get("setores", []) if isinstance(dados, dict) else dados
    if not isinstance(pontos, list) or not pontos:
        return None, 10
    primeiro = pontos[0]
    if not isinstance(primeiro, dict):
        return None, 10
    lat = primeiro.get("latitude") or primeiro.get("lat")
    lon = primeiro.get("longitude") or primeiro.get("lon")
    if not (lat and lon):
        return None, 10
    return [float(lat), float(lon)], 11


def _mensagem_assistente(resposta: dict, chamadas: list[dict]) -> dict:
    return {
        "role": "assistant",
        "content": resposta.get("content") or "",
        "tool_calls": [
            {
                "id": chamada["id"],
                "type": "function",
                "function": {
                    "name": chamada["name"],
                    "arguments": json.dumps(chamada.get("arguments") or {}),
                },
            }
            for chamada in chamadas
        ],
    }


def _resposta_de_fallback(ferramentas: list[str], dados, houve_chamada: bool) -> str:
    """Última linha de defesa quando o modelo devolve `content` vazio.

    Acontece com modelos de raciocínio que estouram `max_tokens` antes de
    escrever texto — sem isto a tela fica em branco.
    """
    ferramenta = ferramentas[-1] if ferramentas else None

    if isinstance(dados, dict) and "erro" in dados:
        return f"Não foi possível executar a ferramenta: {dados['erro']}"
    if isinstance(dados, dict) and dados.get("total_setores") is not None:
        total = dados["total_setores"]
        if total:
            return (
                f"A consulta retornou {total} setores. Os dados estão na tabela e no mapa ao lado."
            )
        return (
            "Nenhum setor encontrado com esses filtros. "
            "Ajuste o município, o distrito ou o nível de acesso."
        )
    if isinstance(dados, list):
        return f"A consulta retornou {len(dados)} registros. Veja a tabela e o mapa."
    if ferramenta:
        return "A consulta foi executada, mas o modelo não gerou texto."
    if houve_chamada:
        return "Não foi possível gerar uma resposta. Tente novamente."
    return "Não foi possível gerar uma resposta. Reformule a pergunta e tente de novo."


def _clamp_limite(valor, padrao: int) -> int:
    """Limita o parâmetro `limite` de volta ao servidor.

    O modelo pode pedir `limite=500` e derrubar o frontend (e o contexto do
    LLM) com meio milhar de linhas.
    """
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return padrao
    if numero <= 0:
        return padrao
    return min(numero, LIMITE_MAXIMO_LISTA)


def _sem_coordenadas(item: dict) -> dict:
    """Remove lat/lon: o mapa é do frontend, não do contexto do LLM.

    Cada par de coordenadas custava ~12 tokens por linha e bastava um `limite`
    grande para estourar o ITPM do tier free (7000 tokens/min).
    """
    return {k: v for k, v in item.items() if k not in ("latitude", "longitude")}


def _resumir_para_llm(dados: list[dict] | dict) -> list[dict] | dict:
    """Projeção compacta do resultado da ferramenta para o contexto do LLM.

    Trata as duas formas de retorno: dict com `setores` (com resumo agregado
    já pronto) e listas crus (`ranking_municipios`, `comparar_municipios`,
    `buscar_setores_proximos`), que antes iam inteiras para o prompt.
    """
    if isinstance(dados, dict) and "setores" in dados:
        # A amostra já vem ordenada do pior para o melhor acesso (ORDER BY).
        amostra = [_sem_coordenadas(s) for s in dados["setores"][:LLM_AMOSTRA_LLM]]
        return {
            "municipio": dados.get("municipio"),
            "distrito": dados.get("distrito"),
            "categoria": dados.get("categoria"),
            "total_setores": dados.get("total_setores"),
            "resumo": dados.get("resumo"),
            "amostra_ordenada_do_pior_para_o_melhor_acesso": amostra,
        }

    if isinstance(dados, list):
        itens = [_sem_coordenadas(x) for x in dados[:LLM_AMOSTRA_LLM] if isinstance(x, dict)]
        return {"total_itens": len(dados), "itens": itens}

    return dados


def _executar_tool(name: str, args: dict, db: Session) -> list[dict] | dict:
    if name == "buscar_setores_proximos":
        municipio = args.get("municipio")
        if not municipio:
            return {"erro": "Parâmetro 'municipio' é obrigatório"}
        rows = buscar_setores_proximos_db(
            db,
            municipio=municipio,
            raio_km=args.get("raio_km", 30),
            limite_e2sfca=args.get("limite_e2sfca"),
            limite=_clamp_limite(args.get("limite"), 50),
        )
        return [
            {
                "cd_setor": r.cd_setor,
                "nm_mun": r.nm_mun,
                "nm_dist": r.nm_dist,
                "acessibilidade_e2sfca": r.acessibilidade_e2sfca,
                "categoria_acesso": r.categoria_acesso,
                "dist_minima_metros": r.dist_minima_metros,
                "total_medicos_dentro": r.total_medicos_dentro,
                "v0001": r.v0001,
                "latitude": getattr(r, "latitude", None),
                "longitude": getattr(r, "longitude", None),
            }
            for r in rows
        ]

    elif name == "ranking_municipios":
        rows = ranking_municipios_db(
            db,
            indicador=args.get("indicador", "medicos_por_1k"),
            ordem=args.get("ordem", "asc"),
            limite=_clamp_limite(args.get("limite"), 10),
        )
        return [
            {
                "cod_mun_ibge": r.cod_mun_ibge,
                "nm_mun": r.nm_mun,
                "medicos_por_1k": r.medicos_por_1k,
                "total_medicos": r.total_medicos,
                "total_cnes": r.total_cnes,
                "populacao": r.populacao,
                "categoria_densidade": r.categoria_densidade,
            }
            for r in rows
        ]

    elif name == "comparar_municipios":
        municipios = args.get("municipios", [])
        if not isinstance(municipios, list) or not municipios:
            return {"erro": "Parâmetro 'municipios' deve ser uma lista não vazia"}
        rows = comparar_municipios_db(db, municipios=municipios)
        return [
            {
                "cod_mun_ibge": r.cod_mun_ibge,
                "nm_mun": r.nm_mun,
                "medicos_por_1k": r.medicos_por_1k,
                "total_medicos": r.total_medicos,
                "total_cnes": r.total_cnes,
                "populacao": r.populacao,
                "area_km2": r.area_km2,
                "categoria_densidade": r.categoria_densidade,
            }
            for r in rows
        ]

    elif name == "buscar_setores_municipio":
        municipio = args.get("municipio")
        distrito = args.get("distrito")
        if not municipio and not distrito:
            return {"erro": "Informe ao menos um filtro: 'municipio' ou 'distrito'"}
        categoria = args.get("categoria")
        resumo = resumo_setores_db(db, municipio=municipio, distrito=distrito, categoria=categoria)
        rows = buscar_setores_municipio_db(
            db,
            municipio=municipio,
            distrito=distrito,
            categoria=categoria,
            limite=LIMITE_MAXIMO_LISTA,
        )
        setores = [
            {
                "cd_setor": r.cd_setor,
                "nm_mun": r.nm_mun,
                "nm_dist": r.nm_dist,
                "acessibilidade_e2sfca": r.acessibilidade_e2sfca,
                "categoria_acesso": r.categoria_acesso,
                "v0001": r.v0001,
                "total_medicos_dentro": r.total_medicos_dentro,
                "latitude": getattr(r, "latitude", None),
                "longitude": getattr(r, "longitude", None),
            }
            for r in rows
        ]
        return {
            "municipio": municipio,
            "distrito": distrito,
            "categoria": categoria,
            "total_setores": resumo["total_setores"],
            "resumo": resumo,
            "setores": setores,
        }

    return {"erro": f"Tool desconhecida: {name}"}
