"""adiciona nivel numerico de classificacao

Revision ID: 7b5c441002eb
Revises: 001
Create Date: 2026-08-02 02:30:20.882119
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7b5c441002eb"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "municipios",
        sa.Column("categoria_densidade_nivel", sa.Integer(), nullable=True),
    )
    op.add_column(
        "setores",
        sa.Column("categoria_acesso_nivel", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE setores
        SET categoria_acesso_nivel =
            NULLIF(substring(categoria_acesso from '^\\d+'), '')::int
        WHERE categoria_acesso ~ '^\\d'
        """
    )
    op.execute(
        """
        UPDATE municipios
        SET categoria_densidade_nivel =
            NULLIF(substring(categoria_densidade from '^\\d+'), '')::int
        WHERE categoria_densidade ~ '^\\d'
        """
    )

    op.create_check_constraint(
        "ck_municipios_densidade_nivel",
        "municipios",
        "categoria_densidade_nivel BETWEEN 1 AND 5",
    )
    op.create_check_constraint(
        "ck_setores_acesso_nivel",
        "setores",
        "categoria_acesso_nivel BETWEEN 1 AND 6",
    )


def downgrade() -> None:
    op.drop_constraint("ck_setores_acesso_nivel", "setores", type_="check")
    op.drop_constraint("ck_municipios_densidade_nivel", "municipios", type_="check")
    op.drop_column("setores", "categoria_acesso_nivel")
    op.drop_column("municipios", "categoria_densidade_nivel")
