"""altera tipo da geometria para generico

Revision ID: 9f2c1a3b7e01
Revises: 7b5c441002eb
Create Date: 2026-08-02 02:40:00.000000
"""

from collections.abc import Sequence

from geoalchemy2 import Geometry

from alembic import op

revision: str = "9f2c1a3b7e01"
down_revision: str | None = "7b5c441002eb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("idx_setores_geometry", table_name="setores")
    op.alter_column(
        "setores",
        "geometry",
        type_=Geometry(srid=4326),
        postgresql_using="geometry::geometry(GEOMETRY, 4326)",
    )
    op.create_index(
        "idx_setores_geometry",
        "setores",
        ["geometry"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("idx_setores_geometry", table_name="setores")
    op.alter_column(
        "setores",
        "geometry",
        type_=Geometry("POLYGON", srid=4326),
        postgresql_using="geometry::geometry(POLYGON, 4326)",
    )
    op.create_index(
        "idx_setores_geometry",
        "setores",
        ["geometry"],
        postgresql_using="gist",
    )
