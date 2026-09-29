import re

from sqlalchemy import asc, desc, text
from sqlalchemy.orm import Session

from src.models import Municipio, Setor

_NIVEL_RE = re.compile(r"(\d+)")


def _row_to_setor_with_coords(row) -> Setor:
    data = dict(row)
    lat = data.pop("latitude", None)
    lon = data.pop("longitude", None)
    s = Setor(**data)
    s.latitude = lat
    s.longitude = lon
    return s


def buscar_setores_proximos_db(
    db: Session,
    municipio: str,
    raio_km: float = 30,
    limite_e2sfca: float | None = None,
    limite: int = 50,
) -> list[Setor]:
    params: dict = {"municipio": municipio, "raio_metros": raio_km * 1000, "limite": limite}

    if limite_e2sfca is not None:
        params["limite_e2sfca"] = limite_e2sfca
        query = text("""
            SELECT s.*,
                   ST_Y(ST_Centroid(s.geometry)) as latitude,
                   ST_X(ST_Centroid(s.geometry)) as longitude
            FROM setores s
            WHERE s.geometry IS NOT NULL
              AND ST_DWithin(
                s.geometry::geography,
                (SELECT ST_SetSRID(ST_Centroid(ST_Union(geometry)), 4326) FROM setores
                 WHERE UPPER(nm_mun) = UPPER(:municipio) AND geometry IS NOT NULL)::geography,
                :raio_metros
              )
              AND s.acessibilidade_e2sfca < :limite_e2sfca
            ORDER BY s.acessibilidade_e2sfca ASC
            LIMIT :limite
        """)
    else:
        query = text("""
            SELECT s.*,
                   ST_Y(ST_Centroid(s.geometry)) as latitude,
                   ST_X(ST_Centroid(s.geometry)) as longitude
            FROM setores s
            WHERE s.geometry IS NOT NULL
              AND ST_DWithin(
                s.geometry::geography,
                (SELECT ST_SetSRID(ST_Centroid(ST_Union(geometry)), 4326) FROM setores
                 WHERE UPPER(nm_mun) = UPPER(:municipio) AND geometry IS NOT NULL)::geography,
                :raio_metros
              )
            ORDER BY s.acessibilidade_e2sfca ASC
            LIMIT :limite
        """)

    rows = db.execute(query, params).mappings().all()
    return [_row_to_setor_with_coords(r) for r in rows]


def ranking_municipios_db(
    db: Session,
    indicador: str = "medicos_por_1k",
    ordem: str = "asc",
    limite: int = 10,
) -> list[Municipio]:
    colunas_validas = {
        "medicos_por_1k": Municipio.medicos_por_1k,
        "total_medicos": Municipio.total_medicos,
        "total_cnes": Municipio.total_cnes,
        "populacao": Municipio.populacao,
    }
    coluna = colunas_validas.get(indicador, Municipio.medicos_por_1k)
    order_fn = asc if ordem == "asc" else desc

    return (
        db.query(Municipio)
        .filter(coluna.isnot(None))
        .order_by(order_fn(coluna))
        .limit(limite)
        .all()
    )


def comparar_municipios_db(
    db: Session,
    municipios: list[str],
) -> list[Municipio]:
    if not municipios:
        return []

    placeholders = ", ".join([f"UPPER(:m{i})" for i in range(len(municipios))])
    params = {f"m{i}": m for i, m in enumerate(municipios)}

    rows = (
        db.execute(
            text(f"""
            SELECT * FROM municipios
            WHERE UPPER(nm_mun) IN ({placeholders})
        """),
            params,
        )
        .mappings()
        .all()
    )

    return [Municipio(**dict(r)) for r in rows]


def _filtros_setores(
    municipio: str | None,
    distrito: str | None,
    categoria: str | int | None,
) -> tuple[list[str], dict]:
    """Monta as condições WHERE (somente strings fixas + parâmetros ligados)."""
    conds: list[str] = []
    params: dict = {}

    if municipio:
        conds.append("UPPER(s.nm_mun) = UPPER(:municipio)")
        params["municipio"] = municipio
    if distrito:
        conds.append("UPPER(s.nm_dist) = UPPER(:distrito)")
        params["distrito"] = distrito

    if categoria is not None:
        nivel = categoria if isinstance(categoria, int) else None
        if nivel is None:
            match = _NIVEL_RE.match(str(categoria).strip())
            if match:
                nivel = int(match.group(1))
        if nivel is not None:
            conds.append("s.categoria_acesso_nivel = :categoria")
            params["categoria"] = nivel
        else:
            conds.append("s.categoria_acesso ILIKE :categoria")
            params["categoria"] = f"%{str(categoria).strip()}%"

    return conds, params


def resumo_setores_db(
    db: Session,
    municipio: str | None = None,
    distrito: str | None = None,
    categoria: str | int | None = None,
) -> dict:
    """Agregados de todos os setores que casam o filtro (não só a amostra)."""
    if not municipio and not distrito:
        return {"total_setores": 0}
    conds, params = _filtros_setores(municipio, distrito, categoria)
    if not conds:
        return {"total_setores": 0}
    where = " AND ".join(conds)

    totais = (
        db.execute(
            text(f"""
        SELECT count(*) AS total_setores,
               count(*) FILTER (WHERE s.acessibilidade_e2sfca IS NOT NULL) AS setores_avaliados,
               round(avg(s.acessibilidade_e2sfca)::numeric, 6) AS media_e2sfca,
               min(s.acessibilidade_e2sfca) AS min_e2sfca,
               max(s.acessibilidade_e2sfca) AS max_e2sfca,
               count(*) FILTER (WHERE s.total_medicos_dentro > 0) AS setores_com_medico_dentro,
               count(*) FILTER (WHERE s.categoria_acesso_nivel >= 5) AS setores_acesso_ruim
        FROM setores s
        WHERE {where}
        """),
            params,
        )
        .mappings()
        .one()
    )

    distribuicao = [
        {
            "categoria": r["categoria_acesso"],
            "setores": int(r["n"]),
            "pct": round(100 * int(r["n"]) / max(int(totais["total_setores"]), 1), 1),
        }
        for r in db.execute(
            text(f"""
            SELECT s.categoria_acesso, count(*) AS n
            FROM setores s
            WHERE {where}
            GROUP BY 1
            ORDER BY 1
            """),
            params,
        ).mappings()
    ]

    resumo: dict = {}
    for chave, valor in dict(totais).items():
        if valor is None:
            resumo[chave] = None
        elif chave.endswith("e2sfca"):
            resumo[chave] = float(valor)
        else:
            resumo[chave] = int(valor)
    resumo["distribuicao"] = distribuicao
    return resumo


def buscar_setores_municipio_db(
    db: Session,
    municipio: str | None = None,
    categoria: str | int | None = None,
    distrito: str | None = None,
    limite: int | None = None,
) -> list[Setor]:
    if not municipio and not distrito:
        return []
    conds, params = _filtros_setores(municipio, distrito, categoria)
    if not conds:
        return []

    sql = f"""
        SELECT s.*,
               ST_Y(ST_Centroid(s.geometry)) as latitude,
               ST_X(ST_Centroid(s.geometry)) as longitude
        FROM setores s
        WHERE {" AND ".join(conds)}
        ORDER BY s.acessibilidade_e2sfca ASC NULLS LAST, s.cd_setor ASC
    """
    if limite:
        sql += " LIMIT :limite"
        params["limite"] = limite

    rows = db.execute(text(sql), params).mappings().all()
    return [_row_to_setor_with_coords(r) for r in rows]
