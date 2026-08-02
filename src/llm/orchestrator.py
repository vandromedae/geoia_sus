import json

from sqlalchemy.orm import Session

from src.llm.base import LLMClient
from src.llm.prompts import SYSTEM_PROMPT
from src.llm.tools import ALL_TOOLS
from src.schemas import QueryResponse
from src.services.spatial import (
    buscar_setores_municipio_db,
    buscar_setores_proximos_db,
    comparar_municipios_db,
    ranking_municipios_db,
)

SCOPE_KEYWORDS = [
    "saúde", "saude", "médico", "medico", "médicos", "medicos",
    "hospital", "ubs", "posto de saúde", "posto de saude",
    "atenção primaria", "atencao primaria", "acesso",
    "e2sfca", "densidade", "população", "populacao",
    "setor", "município", "municipio", "campinas", "santos",
    "são paulo", "sao paulo", "guarulhos", "sorocaba",
    "ranking", "comparar", "comparação", "comparacao", "compare",
    "cnes", "leito", "leitos", "enfermeiro", "enfermeiros",
    "dentista", "farmácia", "farmacia",
    "mostre", "exiba", "liste",
]


def _checar_escopo(pergunta: str) -> bool:
    pergunta_lower = pergunta.lower()
    return any(kw in pergunta_lower for kw in SCOPE_KEYWORDS)


async def processar_pergunta(
    pergunta: str, db: Session, llm: LLMClient
) -> QueryResponse:
    if not _checar_escopo(pergunta):
        return QueryResponse(
            resposta="Essa pergunta está fora do escopo do GeoIA_SUS. "
            "Posso ajudar com perguntas sobre acesso à saúde, densidade "
            "de médicos, e dados do SUS no Estado de São Paulo.",
            dados=None,
            tool_chamada=None,
        )

    resposta_llm = llm.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": pergunta},
        ],
        tools=ALL_TOOLS,
    )

    if not resposta_llm["tool_calls"]:
        return QueryResponse(
            resposta=resposta_llm["content"],
            dados=None,
            tool_chamada=None,
        )

    tool_call = resposta_llm["tool_calls"][0]
    tool_call_id = tool_call.get("id")
    tool_name = tool_call["name"]
    tool_args = tool_call["arguments"]

    dados = _executar_tool(tool_name, tool_args, db)
    dados_llm = _resumir_para_llm(dados)

    resposta_final = llm.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": pergunta},
            {"role": "assistant", "content": "",
             "tool_calls": [
                 {"id": tool_call_id, "type": "function",
                  "function": {"name": tool_name, "arguments": json.dumps(tool_args)}}
             ]},
            {"role": "tool", "tool_call_id": tool_call_id,
             "content": json.dumps(dados_llm, default=str, ensure_ascii=False)},
        ],
    )

    mapa_centro = None
    mapa_zoom = 10
    pontos = dados
    if isinstance(dados, dict):
        pontos = dados.get("setores", [])
    if isinstance(pontos, list) and pontos:
        sample = pontos[0]
        lat = sample.get("latitude") or sample.get("lat")
        lon = sample.get("longitude") or sample.get("lon")
        if lat and lon:
            mapa_centro = [float(lat), float(lon)]
            mapa_zoom = 11

    return QueryResponse(
        resposta=resposta_final["content"],
        dados=dados,
        tool_chamada=tool_name,
        mapa_centro=mapa_centro,
        mapa_zoom=mapa_zoom,
    )


def _resumir_para_llm(dados: list[dict] | dict) -> list[dict] | dict:
    """Projeção compacta do resultado da ferramenta para o contexto do LLM."""
    if not isinstance(dados, dict) or "setores" not in dados:
        return dados
    amostra = [
        {k: v for k, v in s.items() if k not in ("latitude", "longitude")}
        for s in dados["setores"][:30]
    ]
    return {
        "municipio": dados.get("municipio"),
        "categoria": dados.get("categoria"),
        "total_setores": dados.get("total_setores"),
        "amostra": amostra,
    }


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
            limite=args.get("limite", 50),
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
            limite=args.get("limite", 10),
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
        if not municipio:
            return {"erro": "Parâmetro 'municipio' é obrigatório"}
        rows = buscar_setores_municipio_db(
            db,
            municipio=municipio,
            categoria=args.get("categoria"),
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
            "categoria": args.get("categoria"),
            "total_setores": len(setores),
            "setores": setores[:100],
        }

    return {"erro": f"Tool desconhecida: {name}"}
