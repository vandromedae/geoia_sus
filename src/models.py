from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Municipio(Base):
    __tablename__ = "municipios"

    # Código oficial IBGE do município, 7 dígitos (ex.: 3500105 = Adamantina).
    # A origem publicava 6 dígitos (o check digit cortado), que não junta com
    # nenhuma base externa; ver `src/services/data.py::atualizar_codigos_ibge`.
    cod_mun_ibge: Mapped[str] = mapped_column(String(7), primary_key=True)
    nm_mun: Mapped[str] = mapped_column(String)
    populacao: Mapped[float | None] = mapped_column(Float)
    area_km2: Mapped[float | None] = mapped_column(Float)
    num_setores: Mapped[int | None] = mapped_column(Integer)
    total_medicos: Mapped[int | None] = mapped_column(Integer)
    total_cnes: Mapped[int | None] = mapped_column(Integer)
    medicos_por_1k: Mapped[float | None] = mapped_column(Float)
    categoria_densidade: Mapped[str | None] = mapped_column(String)
    categoria_densidade_nivel: Mapped[int | None] = mapped_column(Integer)
    uf: Mapped[str | None] = mapped_column(String(2))
    # Centroide pré-computado dos setores do município. Usado como ponto de
    # referência de `buscar_setores_proximos`; sem ele a query precisava fazer
    # ST_Centroid(ST_Collect(...)) de todos os polígonos a cada chamada (~2 s
    # em São Paulo). Backfill em `src/services/data.py::atualizar_centroides`.
    centroide: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))

    __table_args__ = (
        CheckConstraint(
            "categoria_densidade_nivel BETWEEN 1 AND 5",
            name="ck_municipios_densidade_nivel",
        ),
    )


class Setor(Base):
    __tablename__ = "setores"

    cd_setor: Mapped[str] = mapped_column(String(20), primary_key=True)
    situacao: Mapped[str | None] = mapped_column(String)
    cd_sit: Mapped[str | None] = mapped_column(String)
    cd_tipo: Mapped[str | None] = mapped_column(String)
    area_km2: Mapped[float | None] = mapped_column(Float)
    cd_regiao: Mapped[str | None] = mapped_column(String)
    nm_regiao: Mapped[str | None] = mapped_column(String)
    cd_uf: Mapped[str | None] = mapped_column(String)
    nm_uf: Mapped[str | None] = mapped_column(String)
    cd_mun: Mapped[str | None] = mapped_column(String)
    nm_mun: Mapped[str | None] = mapped_column(String)
    cd_dist: Mapped[str | None] = mapped_column(String)
    nm_dist: Mapped[str | None] = mapped_column(String)
    cd_subdist: Mapped[str | None] = mapped_column(String)
    nm_subdist: Mapped[str | None] = mapped_column(String)
    cd_bairro: Mapped[str | None] = mapped_column(String)
    nm_bairro: Mapped[str | None] = mapped_column(String)
    cd_nu: Mapped[str | None] = mapped_column(String)
    nm_nu: Mapped[str | None] = mapped_column(String)
    cd_fcu: Mapped[str | None] = mapped_column(String)
    nm_fcu: Mapped[str | None] = mapped_column(String)
    cd_aglom: Mapped[str | None] = mapped_column(String)
    nm_aglom: Mapped[str | None] = mapped_column(String)
    cd_rgint: Mapped[str | None] = mapped_column(String)
    nm_rgint: Mapped[str | None] = mapped_column(String)
    cd_rgi: Mapped[str | None] = mapped_column(String)
    nm_rgi: Mapped[str | None] = mapped_column(String)
    cd_concurb: Mapped[str | None] = mapped_column(String)
    nm_concurb: Mapped[str | None] = mapped_column(String)
    v0001: Mapped[float | None] = mapped_column(Float)
    v0002: Mapped[float | None] = mapped_column(Float)
    v0003: Mapped[float | None] = mapped_column(Float)
    v0004: Mapped[float | None] = mapped_column(Float)
    v0005: Mapped[float | None] = mapped_column(Float)
    v0006: Mapped[float | None] = mapped_column(Float)
    v0007: Mapped[float | None] = mapped_column(Float)
    cod_mun_ibge: Mapped[str | None] = mapped_column(String(7))
    acessibilidade_e2sfca: Mapped[float | None] = mapped_column(Float)
    categoria_acesso: Mapped[str | None] = mapped_column(String)
    categoria_acesso_nivel: Mapped[int | None] = mapped_column(Integer)
    dist_minima_metros: Mapped[float | None] = mapped_column(Float)
    total_medicos_dentro: Mapped[int | None] = mapped_column(Integer)
    total_cnes_dentro: Mapped[int | None] = mapped_column(Integer)
    geometry: Mapped[str | None] = mapped_column(Geometry(srid=4326))

    __table_args__ = (
        Index("idx_setores_cod_mun", "cod_mun_ibge"),
        Index("idx_setores_nm_mun", "nm_mun"),
        Index("idx_setores_e2sfca", "acessibilidade_e2sfca"),
        CheckConstraint(
            "categoria_acesso_nivel BETWEEN 1 AND 6",
            name="ck_setores_acesso_nivel",
        ),
    )


class Cnes(Base):
    __tablename__ = "cnes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cnes: Mapped[str | None] = mapped_column(String)
    municipio: Mapped[str | None] = mapped_column(String)
    nome_fantasia: Mapped[str | None] = mapped_column(String)
    total_medicos: Mapped[int | None] = mapped_column(Integer)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    geometry: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
