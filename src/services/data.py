import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from geoalchemy2.elements import WKTElement
from shapely import wkb
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Cnes, Municipio, Setor

_NIVEL_RE = re.compile(r"(\d+)")


def _nivel(texto: str) -> int | None:
    m = _NIVEL_RE.match(texto.strip())
    return int(m.group(1)) if m else None


def importar_municipios(caminho: Path, session: Session) -> int:
    df = pd.read_parquet(caminho)
    count = 0
    for _, row in df.iterrows():
        obj = session.get(Municipio, str(row["cod_mun_ibge"]))
        if obj is None:
            obj = Municipio(cod_mun_ibge=str(row["cod_mun_ibge"]))
        obj.nm_mun = str(row["nm_mun"])
        obj.populacao = float(row["populacao"]) if pd.notna(row["populacao"]) else None
        obj.area_km2 = float(row["area_km2"]) if pd.notna(row["area_km2"]) else None
        obj.num_setores = int(row["num_setores"]) if pd.notna(row["num_setores"]) else None
        obj.total_medicos = int(row["total_medicos"]) if pd.notna(row["total_medicos"]) else None
        obj.total_cnes = int(row["total_cnes"]) if pd.notna(row["total_cnes"]) else None
        obj.medicos_por_1k = float(row["medicos_por_1k"]) if pd.notna(row["medicos_por_1k"]) else None
        obj.categoria_densidade = str(row["categoria_densidade"]) if pd.notna(row["categoria_densidade"]) else None
        obj.categoria_densidade_nivel = (
            _nivel(str(row["categoria_densidade"]))
            if pd.notna(row["categoria_densidade"])
            else None
        )
        obj.uf = str(row["uf"]) if pd.notna(row["uf"]) else None
        session.merge(obj)
        count += 1
    session.commit()
    return count


def importar_setores(caminho: Path, session: Session, limite: int | None = None) -> int:
    try:
        gdf = gpd.read_parquet(caminho)
    except ValueError:
        df = pd.read_parquet(caminho)
        gdf = gpd.GeoDataFrame(df, geometry=None)

    if limite:
        gdf = gdf.head(limite)

    count = 0
    for _, row in gdf.iterrows():
        geometry_wkt = None
        if pd.notna(row.get("geometry")):
            geom = row["geometry"]
            if isinstance(geom, bytes):
                geom = wkb.loads(geom)
            geometry_wkt = geom.wkt if geom is not None else None

        obj = session.get(Setor, str(row["CD_SETOR"]))
        if obj is None:
            obj = Setor(cd_setor=str(row["CD_SETOR"]))

        obj.situacao = str(row["SITUACAO"]) if pd.notna(row.get("SITUACAO")) else None
        obj.cd_sit = str(row["CD_SIT"]) if pd.notna(row.get("CD_SIT")) else None
        obj.cd_tipo = str(row["CD_TIPO"]) if pd.notna(row.get("CD_TIPO")) else None
        obj.area_km2 = float(row["AREA_KM2"]) if pd.notna(row.get("AREA_KM2")) else None
        obj.cd_regiao = str(row["CD_REGIAO"]) if pd.notna(row.get("CD_REGIAO")) else None
        obj.nm_regiao = str(row["NM_REGIAO"]) if pd.notna(row.get("NM_REGIAO")) else None
        obj.cd_uf = str(row["CD_UF"]) if pd.notna(row.get("CD_UF")) else None
        obj.nm_uf = str(row["NM_UF"]) if pd.notna(row.get("NM_UF")) else None
        obj.cd_mun = str(row["CD_MUN"]) if pd.notna(row.get("CD_MUN")) else None
        obj.nm_mun = str(row["NM_MUN"]) if pd.notna(row.get("NM_MUN")) else None
        obj.cd_dist = str(row["CD_DIST"]) if pd.notna(row.get("CD_DIST")) else None
        obj.nm_dist = str(row["NM_DIST"]) if pd.notna(row.get("NM_DIST")) else None
        obj.cd_subdist = str(row["CD_SUBDIST"]) if pd.notna(row.get("CD_SUBDIST")) else None
        obj.nm_subdist = str(row["NM_SUBDIST"]) if pd.notna(row.get("NM_SUBDIST")) else None
        obj.cd_bairro = str(row["CD_BAIRRO"]) if pd.notna(row.get("CD_BAIRRO")) else None
        obj.nm_bairro = str(row["NM_BAIRRO"]) if pd.notna(row.get("NM_BAIRRO")) else None
        obj.cd_nu = str(row["CD_NU"]) if pd.notna(row.get("CD_NU")) else None
        obj.nm_nu = str(row["NM_NU"]) if pd.notna(row.get("NM_NU")) else None
        obj.cd_fcu = str(row["CD_FCU"]) if pd.notna(row.get("CD_FCU")) else None
        obj.nm_fcu = str(row["NM_FCU"]) if pd.notna(row.get("NM_FCU")) else None
        obj.cd_aglom = str(row["CD_AGLOM"]) if pd.notna(row.get("CD_AGLOM")) else None
        obj.nm_aglom = str(row["NM_AGLOM"]) if pd.notna(row.get("NM_AGLOM")) else None
        obj.cd_rgint = str(row["CD_RGINT"]) if pd.notna(row.get("CD_RGINT")) else None
        obj.nm_rgint = str(row["NM_RGINT"]) if pd.notna(row.get("NM_RGINT")) else None
        obj.cd_rgi = str(row["CD_RGI"]) if pd.notna(row.get("CD_RGI")) else None
        obj.nm_rgi = str(row["NM_RGI"]) if pd.notna(row.get("NM_RGI")) else None
        obj.cd_concurb = str(row["CD_CONCURB"]) if pd.notna(row.get("CD_CONCURB")) else None
        obj.nm_concurb = str(row["NM_CONCURB"]) if pd.notna(row.get("NM_CONCURB")) else None
        obj.v0001 = float(row["v0001"]) if pd.notna(row.get("v0001")) else None
        obj.v0002 = float(row["v0002"]) if pd.notna(row.get("v0002")) else None
        obj.v0003 = float(row["v0003"]) if pd.notna(row.get("v0003")) else None
        obj.v0004 = float(row["v0004"]) if pd.notna(row.get("v0004")) else None
        obj.v0005 = float(row["v0005"]) if pd.notna(row.get("v0005")) else None
        obj.v0006 = float(row["v0006"]) if pd.notna(row.get("v0006")) else None
        obj.v0007 = float(row["v0007"]) if pd.notna(row.get("v0007")) else None
        obj.cod_mun_ibge = str(row["cod_mun_ibge"]) if pd.notna(row.get("cod_mun_ibge")) else None
        obj.acessibilidade_e2sfca = float(row["acessibilidade_e2sfca"]) if pd.notna(row.get("acessibilidade_e2sfca")) else None
        obj.categoria_acesso = str(row["categoria_acesso"]) if pd.notna(row.get("categoria_acesso")) else None
        obj.categoria_acesso_nivel = (
            _nivel(str(row["categoria_acesso"]))
            if pd.notna(row.get("categoria_acesso"))
            else None
        )
        obj.dist_minima_metros = float(row["dist_minima_metros"]) if pd.notna(row.get("dist_minima_metros")) else None
        obj.total_medicos_dentro = int(row["total_medicos_dentro"]) if pd.notna(row.get("total_medicos_dentro")) else None
        obj.total_cnes_dentro = int(row["total_cnes_dentro"]) if pd.notna(row.get("total_cnes_dentro")) else None

        if geometry_wkt:
            obj.geometry = WKTElement(geometry_wkt, srid=4326)

        session.merge(obj)
        count += 1
        if count % 1000 == 0:
            session.commit()
    session.commit()
    return count


def importar_cnes(caminho: Path, session: Session) -> int:
    df = pd.read_parquet(caminho)
    count = 0
    for _, row in df.iterrows():
        cnes_val = str(row["cnes"]) if pd.notna(row.get("cnes")) else None
        obj = None
        if cnes_val:
            obj = session.scalar(select(Cnes).where(Cnes.cnes == cnes_val))
        if obj is None:
            obj = Cnes(cnes=cnes_val)
        obj.municipio = str(row["municipio"]) if pd.notna(row.get("municipio")) else None
        obj.nome_fantasia = str(row["nome_fantaia"]) if pd.notna(row.get("nome_fantaia")) else None
        obj.total_medicos = int(row["total_medicos"]) if pd.notna(row.get("total_medicos")) else None
        obj.latitude = float(row["latitude"]) if pd.notna(row.get("latitude")) else None
        obj.longitude = float(row["longitude"]) if pd.notna(row.get("longitude")) else None

        if obj.latitude and obj.longitude:
            point = Point(obj.longitude, obj.latitude)
            obj.geometry = WKTElement(point.wkt, srid=4326)

        session.add(obj)
        count += 1
        if count % 1000 == 0:
            session.commit()
    session.commit()
    return count
