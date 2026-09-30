import re
from collections.abc import Iterable, Iterator
from pathlib import Path

import geopandas as gpd
import pandas as pd
from geoalchemy2.elements import WKTElement
from shapely import wkb
from shapely.geometry import Point
from sqlalchemy import select, text, tuple_
from sqlalchemy.orm import Session

from src.models import Cnes, Municipio, Setor

_NIVEL_RE = re.compile(r"(\d+)")

# Linhas por lote de upsert. O import antigo fazia um `session.get` + `merge`
# por linha: 103 mil setores levavam ~5,6 minutos (e o CNES 40 s, só de
# SELECT), segurando o boot da API inteira no passo [3/4] do entrypoint.
_LOTE = 10_000


class ColunasFaltandoError(ValueError):
    """O parquet da release não tem as colunas que o import espera."""


class CodigosIBGEConflitantesError(RuntimeError):
    """Dois municípios diferentes disputam o mesmo prefixo de 6 dígitos."""


def _nivel(texto) -> int | None:
    if texto is None:
        return None
    m = _NIVEL_RE.match(str(texto).strip())
    return int(m.group(1)) if m else None


def _validar_colunas(caminho: Path, df, obrigatorias: Iterable[str]) -> None:
    """Falha alto e cedo, com o nome do arquivo e das colunas.

    Antes a ausência de uma coluna virava `KeyError: 'nome_fantaia'` lá no
    meio do import, depois de já ter escrito metade da tabela.
    """
    faltando = [c for c in obrigatorias if c not in df.columns]
    if faltando:
        raise ColunasFaltandoError(
            f"{caminho.name}: colunas obrigatórias ausentes: {faltando}. "
            f"Colunas presentes: {list(df.columns)}"
        )


def _texto(valor) -> str | None:
    if valor is None or pd.isna(valor):
        return None
    return str(valor)


def _flutuante(valor) -> float | None:
    if valor is None or pd.isna(valor):
        return None
    return float(valor)


def _inteiro(valor) -> int | None:
    if valor is None or pd.isna(valor):
        return None
    return int(valor)


def _geometria(valor):
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, bytes | bytearray):
        valor = wkb.loads(bytes(valor))
    wkt = getattr(valor, "wkt", None)
    if not wkt:
        return None
    return WKTElement(wkt, srid=4326)


def _codigo_ibge(row) -> str | None:
    """Código IBGE completo (7 dígitos) de uma linha de setores.

    `cod_mun_ibge` na release vem truncado em 6 (`350010`); o oficial está em
    `CD_MUN` (`3500105` = Adamantina), que o import grava em `cd_mun`.
    """
    cd_mun = _texto(row.get("CD_MUN"))
    if cd_mun is not None and len(cd_mun) == 7 and cd_mun.isdigit():
        return cd_mun
    return _texto(row.get("cod_mun_ibge"))


# Prefixo de 6 dígitos -> código de 7, a partir do que já está no banco. O
# parquet de municípios não traz o check digit, então quem tem ele são os
# setores (e um município já migrado, que serve de fonte sozinho — evita
# duplicar a linha quando só `municipios` é reimportado).
_SQL_MAPA_IBGE7 = """
    SELECT DISTINCT left(c, 6) AS curto, c AS novo
    FROM (
        SELECT cod_mun_ibge AS c FROM municipios WHERE length(cod_mun_ibge) = 7
        UNION
        SELECT cod_mun_ibge AS c FROM setores WHERE length(cod_mun_ibge) = 7
        UNION
        SELECT cd_mun AS c FROM setores WHERE length(cd_mun) = 7
    ) t
"""

_SQL_PREFIXE_AMBIGUO = """
    SELECT left(cod_mun_ibge, 6) AS curto, count(DISTINCT cod_mun_ibge) AS n
    FROM setores
    WHERE length(cod_mun_ibge) = 7
    GROUP BY 1
    HAVING count(DISTINCT cod_mun_ibge) > 1
"""


def _mapa_ibge7(session: Session) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for curto, novo in session.execute(text(_SQL_MAPA_IBGE7)).all():
        anterior = mapa.get(curto)
        if anterior is not None and anterior != novo:
            raise CodigosIBGEConflitantesError(
                f"prefixo {curto} aponta para {anterior} e {novo} ao mesmo tempo"
            )
        mapa[curto] = novo
    return mapa


def _existe(session: Session, modelo, colunas: list, chaves: list[tuple]) -> set[tuple]:
    encontradas: set[tuple] = set()
    expressao = tuple_(*colunas)
    for i in range(0, len(chaves), 2000):
        pedaco = chaves[i : i + 2000]
        linhas = session.execute(select(*colunas).where(expressao.in_(pedaco))).all()
        encontradas.update(tuple(linha) for linha in linhas)
    return encontradas


def _upsert(session: Session, modelo, registros: list[dict], chaves: list[str]) -> None:
    if not registros:
        return
    colunas = [modelo.__table__.c[chave] for chave in chaves]
    filtro = [tuple(reg[chave] for chave in chaves) for reg in registros]
    existentes = _existe(session, modelo, colunas, filtro)
    novos = [r for r in registros if tuple(r[k] for k in chaves) not in existentes]
    atualizados = [r for r in registros if tuple(r[k] for k in chaves) in existentes]
    if novos:
        session.bulk_insert_mappings(modelo, novos)
    if atualizados:
        session.bulk_update_mappings(modelo, atualizados)


def _blocos(itens: Iterable, tamanho: int = _LOTE) -> Iterator[list]:
    bloco: list = []
    for item in itens:
        bloco.append(item)
        if len(bloco) >= tamanho:
            yield bloco
            bloco = []
    if bloco:
        yield bloco


def importar_municipios(caminho: Path, session: Session) -> int:
    df = pd.read_parquet(caminho)
    _validar_colunas(caminho, df, ["cod_mun_ibge", "nm_mun"])

    inteiros = {"num_setores", "total_medicos", "total_cnes"}
    flutuantes = {"populacao", "area_km2", "medicos_por_1k"}
    mapa_ibge7 = _mapa_ibge7(session)
    count = 0
    for bloco in _blocos(df.to_dict("records")):
        registros = []
        for row in bloco:
            bruto = str(row["cod_mun_ibge"])
            cod = mapa_ibge7.get(bruto, bruto)
            registro: dict = {"cod_mun_ibge": cod}
            for coluna in df.columns:
                if coluna in ("cod_mun_ibge", "categoria_densidade"):
                    continue
                valor = row[coluna]
                if coluna in inteiros:
                    registro[coluna] = _inteiro(valor)
                elif coluna in flutuantes:
                    registro[coluna] = _flutuante(valor)
                else:
                    registro[coluna] = _texto(valor)
            registro["categoria_densidade_nivel"] = _nivel(row.get("categoria_densidade"))
            registros.append(registro)
        _upsert(session, Municipio, registros, ["cod_mun_ibge"])
        session.commit()
        count += len(registros)
    return count


def importar_setores(caminho: Path, session: Session, limite: int | None = None) -> int:
    try:
        gdf = gpd.read_parquet(caminho)
    except ValueError:
        gdf = gpd.GeoDataFrame(pd.read_parquet(caminho), geometry=None)
    _validar_colunas(caminho, gdf, ["CD_SETOR", "cod_mun_ibge"])

    if limite:
        gdf = gdf.head(limite)

    flutuantes = {
        "AREA_KM2",
        "v0001",
        "v0002",
        "v0003",
        "v0004",
        "v0005",
        "v0006",
        "v0007",
        "acessibilidade_e2sfca",
        "dist_minima_metros",
    }
    inteiros = {"total_medicos_dentro", "total_cnes_dentro"}
    derivados = {"categoria_acesso_nivel"}

    colunas_texto = [
        c
        for c in gdf.columns
        if c not in flutuantes | inteiros | derivados | {"CD_SETOR", "cod_mun_ibge", "geometry"}
    ]

    count = 0
    for inicio in range(0, len(gdf), _LOTE):
        fatia = gdf.iloc[inicio : inicio + _LOTE]
        registros: list[dict] = []
        for row in fatia.to_dict("records"):
            registro: dict = {
                "cd_setor": str(row["CD_SETOR"]),
                "cod_mun_ibge": _codigo_ibge(row),
            }
            for coluna in colunas_texto:
                registro[coluna.lower()] = _texto(row.get(coluna))
            for coluna in flutuantes:
                registro[coluna.lower()] = _flutuante(row.get(coluna))
            for coluna in inteiros:
                registro[coluna.lower()] = _inteiro(row.get(coluna))
            registro["categoria_acesso_nivel"] = _nivel(row.get("categoria_acesso"))
            registro["geometry"] = _geometria(row.get("geometry"))
            registros.append(registro)

        _upsert(session, Setor, registros, ["cd_setor"])
        session.commit()
        count += len(registros)
    return count


def importar_cnes(caminho: Path, session: Session) -> int:
    df = pd.read_parquet(caminho)
    _validar_colunas(caminho, df, ["cnes"])

    # A origem publica `nome_fantaia` (typo); se um dia corrigirem para
    # `nome_fantasia`, o import continua funcionando.
    coluna_nome = "nome_fantasia" if "nome_fantasia" in df.columns else "nome_fantaia"

    registros: list[dict] = []
    vistos: set[str] = set()
    for row in df.to_dict("records"):
        codigo = _texto(row.get("cnes"))
        if codigo is None or codigo in vistos:
            continue
        vistos.add(codigo)
        registro = {
            "cnes": codigo,
            "municipio": _texto(row.get("municipio")),
            "nome_fantasia": _texto(row.get(coluna_nome)),
            "total_medicos": _inteiro(row.get("total_medicos")),
            "latitude": _flutuante(row.get("latitude")),
            "longitude": _flutuante(row.get("longitude")),
        }
        if registro["latitude"] and registro["longitude"]:
            ponto = Point(registro["longitude"], registro["latitude"])
            registro["geometry"] = WKTElement(ponto.wkt, srid=4326)
        registros.append(registro)

    # `cnes.id` é autoincrement, então o upsert é pelo código do estabelecimento.
    session.query(Cnes).delete(synchronize_session=False)
    for bloco in _blocos(registros):
        session.bulk_insert_mappings(Cnes, bloco)
        session.commit()
    return len(registros)


def atualizar_codigos_ibge(session: Session) -> tuple[int, int]:
    """Completa `cod_mun_ibge` para 7 dígitos nas duas tabelas.

    Precisa rodar depois de `importar_municipios` + `importar_setores` e antes
    de `atualizar_centroides` (que junta as duas tabelas por esse campo). Sem
    ela, um banco recém-criado fica com `350010` e a consulta espacial não acha
    nenhum setor do município.

    Retorna `(setores_corrigidos, municipios_corrigidos)`.
    """
    conflitos = session.execute(text(_SQL_PREFIXE_AMBIGUO)).all()
    if conflitos:
        detalhe = ", ".join(f"{c}->{n}" for c, n in conflitos[:5])
        raise CodigosIBGEConflitantesError(
            f"prefixo de 6 dígitos aponta para mais de um município ({detalhe})"
        )

    setores = session.execute(
        text("""
            UPDATE setores
            SET cod_mun_ibge = cd_mun
            WHERE length(cd_mun) = 7
              AND cod_mun_ibge IS DISTINCT FROM cd_mun
        """)
    )
    municipios = session.execute(
        text("""
            UPDATE municipios m
            SET cod_mun_ibge = s.novo
            FROM (
                SELECT left(cod_mun_ibge, 6) AS curto, min(cod_mun_ibge) AS novo
                FROM setores
                WHERE length(cod_mun_ibge) = 7
                GROUP BY 1
            ) s
            WHERE m.cod_mun_ibge = s.curto
              AND length(s.novo) = 7
        """)
    )
    session.commit()
    return setores.rowcount or 0, municipios.rowcount or 0


def atualizar_centroides(session: Session) -> int:
    """Backfill de `municipios.centroide`, que é o ponto de referência de
    `buscar_setores_proximos`. ~2 s para os 645 municípios de SP."""
    linhas = session.execute(
        text("""
            UPDATE municipios m
            SET centroide = s.c
            FROM (
                SELECT cod_mun_ibge,
                       ST_SetSRID(ST_Centroid(ST_Collect(geometry)), 4326) AS c
                FROM setores
                WHERE geometry IS NOT NULL
                GROUP BY cod_mun_ibge
            ) s
            WHERE m.cod_mun_ibge = s.cod_mun_ibge
        """)
    )
    session.commit()
    return linhas.rowcount or 0
