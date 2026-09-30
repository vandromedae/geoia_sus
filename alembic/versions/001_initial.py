"""Initial schema: municipios, setores, cnes

Revision ID: 001
Revises:
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cnes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cnes", sa.String(), nullable=True),
        sa.Column("municipio", sa.String(), nullable=True),
        sa.Column("nome_fantasia", sa.String(), nullable=True),
        sa.Column("total_medicos", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("geometry", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "municipios",
        sa.Column("cod_mun_ibge", sa.String(length=6), nullable=False),
        sa.Column("nm_mun", sa.String(), nullable=False),
        sa.Column("populacao", sa.Float(), nullable=True),
        sa.Column("area_km2", sa.Float(), nullable=True),
        sa.Column("num_setores", sa.Integer(), nullable=True),
        sa.Column("total_medicos", sa.Integer(), nullable=True),
        sa.Column("total_cnes", sa.Integer(), nullable=True),
        sa.Column("medicos_por_1k", sa.Float(), nullable=True),
        sa.Column("categoria_densidade", sa.String(), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.PrimaryKeyConstraint("cod_mun_ibge"),
    )

    op.create_table(
        "setores",
        sa.Column("cd_setor", sa.String(length=20), nullable=False),
        sa.Column("situacao", sa.String(), nullable=True),
        sa.Column("cd_sit", sa.String(), nullable=True),
        sa.Column("cd_tipo", sa.String(), nullable=True),
        sa.Column("area_km2", sa.Float(), nullable=True),
        sa.Column("cd_regiao", sa.String(), nullable=True),
        sa.Column("nm_regiao", sa.String(), nullable=True),
        sa.Column("cd_uf", sa.String(), nullable=True),
        sa.Column("nm_uf", sa.String(), nullable=True),
        sa.Column("cd_mun", sa.String(), nullable=True),
        sa.Column("nm_mun", sa.String(), nullable=True),
        sa.Column("cd_dist", sa.String(), nullable=True),
        sa.Column("nm_dist", sa.String(), nullable=True),
        sa.Column("cd_subdist", sa.String(), nullable=True),
        sa.Column("nm_subdist", sa.String(), nullable=True),
        sa.Column("cd_bairro", sa.String(), nullable=True),
        sa.Column("nm_bairro", sa.String(), nullable=True),
        sa.Column("cd_nu", sa.String(), nullable=True),
        sa.Column("nm_nu", sa.String(), nullable=True),
        sa.Column("cd_fcu", sa.String(), nullable=True),
        sa.Column("nm_fcu", sa.String(), nullable=True),
        sa.Column("cd_aglom", sa.String(), nullable=True),
        sa.Column("nm_aglom", sa.String(), nullable=True),
        sa.Column("cd_rgint", sa.String(), nullable=True),
        sa.Column("nm_rgint", sa.String(), nullable=True),
        sa.Column("cd_rgi", sa.String(), nullable=True),
        sa.Column("nm_rgi", sa.String(), nullable=True),
        sa.Column("cd_concurb", sa.String(), nullable=True),
        sa.Column("nm_concurb", sa.String(), nullable=True),
        sa.Column("v0001", sa.Float(), nullable=True),
        sa.Column("v0002", sa.Float(), nullable=True),
        sa.Column("v0003", sa.Float(), nullable=True),
        sa.Column("v0004", sa.Float(), nullable=True),
        sa.Column("v0005", sa.Float(), nullable=True),
        sa.Column("v0006", sa.Float(), nullable=True),
        sa.Column("v0007", sa.Float(), nullable=True),
        sa.Column("cod_mun_ibge", sa.String(length=6), nullable=True),
        sa.Column("acessibilidade_e2sfca", sa.Float(), nullable=True),
        sa.Column("categoria_acesso", sa.String(), nullable=True),
        sa.Column("dist_minima_metros", sa.Float(), nullable=True),
        sa.Column("total_medicos_dentro", sa.Integer(), nullable=True),
        sa.Column("total_cnes_dentro", sa.Integer(), nullable=True),
        sa.Column("geometry", Geometry(geometry_type="POLYGON", srid=4326), nullable=True),
        sa.PrimaryKeyConstraint("cd_setor"),
    )
    op.create_index("idx_setores_cod_mun", "setores", ["cod_mun_ibge"], unique=False)
    op.create_index("idx_setores_e2sfca", "setores", ["acessibilidade_e2sfca"], unique=False)
    op.create_index("idx_setores_nm_mun", "setores", ["nm_mun"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_setores_nm_mun", table_name="setores")
    op.drop_index("idx_setores_e2sfca", table_name="setores")
    op.drop_index("idx_setores_cod_mun", table_name="setores")
    op.drop_table("setores")
    op.drop_table("municipios")
    op.drop_table("cnes")
