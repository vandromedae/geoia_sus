import math
import re
from typing import NamedTuple

from sqlalchemy import asc, desc, text
from sqlalchemy.orm import Session

from src.models import Municipio, Setor

_NIVEL_RE = re.compile(r"(\d+)")
# fuzzystrmatch recusa strings acima de 255 caracteres.
_MAX_NOME = 255


class Resolucao(NamedTuple):
    """Tradução de um nome digitado pelo usuário para o nome que está no banco.

    `erro` é uma mensagem pronta para o usuário — é assim que se distingue
    "município não existe" de "município existe mas não tem resultado".
    """

    nome: str | None = None
    codigo: str | None = None
    erro: str | None = None


def _limite_fuzzy(nome: str) -> int:
    return max(2, len(nome) // 3)


def resolver_municipio(db: Session, nome: str) -> Resolucao:
    """Resolve o nome com `unaccent` + caixa e, na falta, fuzzy (`levenshtein`).

    Sem `unaccent`, "sao paulo" não casava com "São Paulo" e o usuário via
    "Nenhum resultado encontrado" para um município que existe.
    """
    nome = (nome or "").strip()[:_MAX_NOME]
    if not nome:
        return Resolucao(erro="Informe o nome do município.")

    exato = (
        db.execute(
            text("""
            SELECT cod_mun_ibge, nm_mun FROM municipios
            WHERE unaccent(upper(nm_mun)) = unaccent(upper(:nome))
            LIMIT 1
        """),
            {"nome": nome},
        )
        .mappings()
        .first()
    )
    if exato:
        return Resolucao(nome=exato["nm_mun"], codigo=exato["cod_mun_ibge"])

    candidato = (
        db.execute(
            text("""
            SELECT cod_mun_ibge, nm_mun,
                   levenshtein(unaccent(upper(nm_mun)), unaccent(upper(:nome))) AS dist
            FROM municipios
            ORDER BY dist
            LIMIT 1
        """),
            {"nome": nome},
        )
        .mappings()
        .first()
    )
    if candidato and int(candidato["dist"]) <= _limite_fuzzy(nome):
        return Resolucao(
            erro=f'Município "{nome}" não encontrado em São Paulo. '
            f'Você quis dizer "{candidato["nm_mun"]}"?'
        )
    return Resolucao(erro=f'Município "{nome}" não encontrado em São Paulo.')


def resolver_distrito(db: Session, distrito: str, municipio: str | None = None) -> Resolucao:
    """Resolve distrito/bairro, avisando quando o nome é ambíguo entre municípios."""
    distrito = (distrito or "").strip()[:_MAX_NOME]
    if not distrito:
        return Resolucao(erro="Informe o nome do distrito.")

    params: dict = {"nome": distrito}
    condicoes = []
    if municipio:
        # `municipio` chega canônico (vindo de `resolver_municipio`), então o
        # UPPER puro já basta e aproveita o índice composto.
        condicoes.append("UPPER(nm_mun) = UPPER(:municipio)")
        params["municipio"] = municipio.strip()[:_MAX_NOME]
    cond_municipio = "".join(f" AND {c}" for c in condicoes)

    def _consulta(condicao: str) -> list:
        return (
            db.execute(
                text(
                    """
                SELECT DISTINCT nm_dist, nm_mun FROM setores
                WHERE nm_dist IS NOT NULL AND nm_dist <> ''
                """
                    f" AND {condicao}{cond_municipio}"
                    """
                ORDER BY nm_mun, nm_dist
                """
                ),
                params,
            )
            .mappings()
            .all()
        )

    # Índex puro primeiro (case-insensitive); `unaccent()` não é indexável,
    # então só é consultado quando o UPPER não achou nada.
    encontrados = _consulta("UPPER(nm_dist) = UPPER(:nome)")
    if not encontrados:
        encontrados = _consulta("unaccent(upper(nm_dist)) = unaccent(upper(:nome))")

    if len(encontrados) == 1:
        return Resolucao(nome=encontrados[0]["nm_dist"])
    if len(encontrados) > 1:
        lugares = ", ".join(sorted({r["nm_mun"] for r in encontrados}))
        return Resolucao(
            erro=f'O distrito "{distrito}" existe em mais de um município '
            f"({lugares}). Informe também o município."
        )

    candidato = (
        db.execute(
            text("""
            SELECT nm_dist,
                   levenshtein(unaccent(upper(nm_dist)), unaccent(upper(:nome))) AS dist
            FROM (SELECT DISTINCT nm_dist FROM setores
                   WHERE nm_dist IS NOT NULL AND nm_dist <> '') d
            ORDER BY dist
            LIMIT 1
        """),
            {"nome": distrito},
        )
        .mappings()
        .first()
    )
    if candidato and int(candidato["dist"]) <= _limite_fuzzy(distrito):
        return Resolucao(
            erro=f'Distrito "{distrito}" não encontrado. Você quis dizer "{candidato["nm_dist"]}"?'
        )
    return Resolucao(erro=f'Distrito "{distrito}" não encontrado.')


def _ponto_referencia(db: Session, codigo: str) -> tuple[float, float] | None:
    """(lat, lon) do centro do município, lendo o centroide pré-computado.

    O `COALESCE` cai no cálculo a partir dos setores apenas quando o centroide
    ainda não foi preenchido (banco recém-criado, antes do import).
    """
    linha = (
        db.execute(
            text("""
            SELECT ST_Y(p.g) AS lat, ST_X(p.g) AS lon
            FROM (
                SELECT COALESCE(
                    m.centroide,
                    (SELECT ST_Centroid(ST_Collect(s.geometry)) FROM setores s
                      WHERE s.cod_mun_ibge = m.cod_mun_ibge AND s.geometry IS NOT NULL)
                ) AS g
                FROM municipios m
                WHERE m.cod_mun_ibge = :codigo
            ) p
        """),
            {"codigo": codigo},
        )
        .mappings()
        .first()
    )
    if not linha or linha["lat"] is None or linha["lon"] is None:
        return None
    return float(linha["lat"]), float(linha["lon"])


def _delta_graus(raio_km: float, lat: float) -> float:
    """Meia-largura (em graus) que cobre o círculo de `raio_km`.

    Dois papéis, uma constante só:

    * `&& ST_Expand(...)` — é o que aciona o índice GiST (sem a caixa a
      consulta de São Paulo levava 6,2 s; com ela, 0,7 s).
    * `ST_DWithin(geom, ponto, delta)` — filtro de distância em graus
      planares. Usar `::geography` aqui custava ~1,1 s (recalcula cada
      vértice em coordenadas esféricas); em graus cai para ~50 ms.

    O divisor é o comprimento de um grau de **longitude** na latitude de
    referência, o menor dos dois eixos — assim o círculo planar é sempre um
    superconjunto do círculo verdadeiro (folga de ~9% no eixo norte-sul).
    """
    cos_lat = max(abs(math.cos(math.radians(lat))), 0.2)
    return raio_km / (111.32 * cos_lat)


def buscar_setores_proximos_db(
    db: Session,
    municipio: str,
    raio_km: float = 30,
    limite_e2sfca: float | None = None,
    limite: int = 50,
) -> list[Setor]:
    resolucao = resolver_municipio(db, municipio)
    if not resolucao.codigo:
        return []
    ponto = _ponto_referencia(db, resolucao.codigo)
    if ponto is None:
        return []
    lat, lon = ponto

    params: dict = {
        "lon": lon,
        "lat": lat,
        "delta": _delta_graus(raio_km, lat),
        "limite": limite,
    }
    condicao_extra = ""
    if limite_e2sfca is not None:
        params["limite_e2sfca"] = limite_e2sfca
        condicao_extra = "AND s.acessibilidade_e2sfca < :limite_e2sfca"

    # Seleciona e ordena sem calcular centroides; só as `limite` linhas finais
    # pagam o ST_Centroid (antes rodava para os ~40 mil setores dentro do raio).
    rows = (
        db.execute(
            text(f"""
        WITH ref AS MATERIALIZED (
            SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS g
        ),
        candidatos AS (
            SELECT s.cd_setor, s.acessibilidade_e2sfca
            FROM setores s, ref
            WHERE s.geometry IS NOT NULL
              AND s.geometry && ST_Expand(ref.g, :delta)
              AND ST_DWithin(s.geometry, ref.g, :delta)
              {condicao_extra}
            ORDER BY s.acessibilidade_e2sfca ASC
            LIMIT :limite
        )
        SELECT s.*,
               ST_Y(ST_Centroid(s.geometry)) AS latitude,
               ST_X(ST_Centroid(s.geometry)) AS longitude
        FROM candidatos c
        JOIN setores s ON s.cd_setor = c.cd_setor
        ORDER BY c.acessibilidade_e2sfca ASC, c.cd_setor ASC
        """),
            params,
        )
        .mappings()
        .all()
    )
    return [_row_to_setor_with_coords(r) for r in rows]


def _row_to_setor_with_coords(row) -> Setor:
    data = dict(row)
    lat = data.pop("latitude", None)
    lon = data.pop("longitude", None)
    s = Setor(**data)
    s.latitude = lat
    s.longitude = lon
    return s


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

    placeholders = ", ".join([f"unaccent(upper(:m{i}))" for i in range(len(municipios))])
    params = {f"m{i}": m for i, m in enumerate(municipios)}

    rows = (
        db.execute(
            text(f"""
            SELECT * FROM municipios
            WHERE unaccent(upper(nm_mun)) IN ({placeholders})
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
