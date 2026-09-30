"""cria extensoes de busca e indices por nome

Revisões anteriores não tinham `unaccent` (busca "sao paulo" != "São Paulo")
nem índices para `upper(nm_mun)`/`upper(nm_dist)`, que faziam seq scan em
103 mil setores a cada consulta.

Revision ID: c8f4d2a91b37
Revises: 9f2c1a3b7e01
Create Date: 2026-09-29 16:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c8f4d2a91b37"
down_revision: str | None = "9f2c1a3b7e01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch")

    # `upper(col) = upper(:p)` não usava índice: seq scan em 103 mil linhas
    # (~80-180 ms por consulta; a ferramenta de setores faz 3 consultas).
    op.execute("CREATE INDEX IF NOT EXISTS idx_setores_nm_mun_upper ON setores (upper(nm_mun))")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_setores_mun_dist_upper "
        "ON setores (upper(nm_mun), upper(nm_dist))"
    )
    # Consulta de distrito sem município filtrando só por nome.
    op.execute("CREATE INDEX IF NOT EXISTS idx_setores_nm_dist_upper ON setores (upper(nm_dist))")

    # Centroide pré-computado: sem ele, cada "setores próximos" calculava
    # ST_Centroid(ST_Collect(...)) de todos os polígonos do município
    # (~2 s para São Paulo, 27.301 polígonos).
    op.execute("ALTER TABLE municipios ADD COLUMN IF NOT EXISTS centroide geometry(Point, 4326)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_municipios_centroide ON municipios USING gist (centroide)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_municipios_centroide")
    op.execute("ALTER TABLE municipios DROP COLUMN IF EXISTS centroide")
    op.execute("DROP INDEX IF EXISTS idx_setores_nm_dist_upper")
    op.execute("DROP INDEX IF EXISTS idx_setores_mun_dist_upper")
    op.execute("DROP INDEX IF EXISTS idx_setores_nm_mun_upper")
