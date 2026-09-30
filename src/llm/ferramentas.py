"""Execução das ferramentas do LLM.

Responsabilidade única: transformar `(nome, argumentos)` em dados prontos,
validando argumentos no caminho. Se uma ferramenta falha devolve
`{"erro": ...}` em vez de levantar — o loop transforma isso em texto
entendível para o usuário, sem 500 na API.
"""

from sqlalchemy.orm import Session

from src.config import LIMITE_MAXIMO_LISTA
from src.services.spatial import (
    buscar_setores_municipio_db,
    buscar_setores_proximos_db,
    comparar_municipios_db,
    ranking_municipios_db,
    resolver_distrito,
    resolver_municipio,
    resumo_setores_db,
)


def clamp_limite(valor, padrao: int) -> int:
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


def executar_tool(name: str, args: dict, db: Session) -> list[dict] | dict:
    if name == "buscar_setores_proximos":
        municipio = (args.get("municipio") or "").strip()
        if not municipio:
            return {"erro": "Parâmetro 'municipio' é obrigatório"}
        resolucao = resolver_municipio(db, municipio)
        if resolucao.erro:
            return {"erro": resolucao.erro}
        rows = buscar_setores_proximos_db(
            db,
            municipio=resolucao.nome,
            raio_km=args.get("raio_km", 30),
            limite_e2sfca=args.get("limite_e2sfca"),
            limite=clamp_limite(args.get("limite"), 50),
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
            limite=clamp_limite(args.get("limite"), 10),
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
        canonicos: list[str] = []
        erros: list[str] = []
        for nome in municipios:
            resolucao = resolver_municipio(db, str(nome))
            if resolucao.erro:
                erros.append(resolucao.erro)
            else:
                canonicos.append(resolucao.nome)
        if erros:
            return {"erro": " ".join(erros)}
        rows = comparar_municipios_db(db, municipios=canonicos)
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
        municipio = (args.get("municipio") or "").strip() or None
        distrito = (args.get("distrito") or "").strip() or None
        if not municipio and not distrito:
            return {"erro": "Informe ao menos um filtro: 'municipio' ou 'distrito'"}
        if municipio:
            resolucao = resolver_municipio(db, municipio)
            if resolucao.erro:
                return {"erro": resolucao.erro}
            municipio = resolucao.nome
        if distrito:
            resolucao = resolver_distrito(db, distrito, municipio)
            if resolucao.erro:
                return {"erro": resolucao.erro}
            distrito = resolucao.nome

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
