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


def buscar_setores_municipio_db(
    db: Session,
    municipio: str,
    categoria: str | int | None = None,
) -> list[Setor]:
    query = text("""
        SELECT s.*,
               ST_Y(ST_Centroid(s.geometry)) as latitude,
               ST_X(ST_Centroid(s.geometry)) as longitude
        FROM setores s
        WHERE UPPER(s.nm_mun) = UPPER(:municipio)
    """)
    params: dict = {"municipio": municipio}

    if categoria is not None:
        nivel = categoria if isinstance(categoria, int) else None
        if nivel is None:
            match = _NIVEL_RE.match(str(categoria).strip())
            if match:
                nivel = int(match.group(1))
        if nivel is not None:
            query = text("""
                SELECT s.*,
                       ST_Y(ST_Centroid(s.geometry)) as latitude,
                       ST_X(ST_Centroid(s.geometry)) as longitude
                FROM setores s
                WHERE UPPER(s.nm_mun) = UPPER(:municipio)
                  AND s.categoria_acesso_nivel = :categoria
            """)
            params["categoria"] = nivel
        else:
            query = text("""
                SELECT s.*,
                       ST_Y(ST_Centroid(s.geometry)) as latitude,
                       ST_X(ST_Centroid(s.geometry)) as longitude
                FROM setores s
                WHERE UPPER(s.nm_mun) = UPPER(:municipio)
                  AND s.categoria_acesso ILIKE :categoria
            """)
            params["categoria"] = f"%{str(categoria).strip()}%"

    rows = db.execute(query, params).mappings().all()
    return [_row_to_setor_with_coords(r) for r in rows]
