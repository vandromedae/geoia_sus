"""cod_mun_ibge de 6 para 7 digitos (codigo IBGE oficial)

A origem publicava o codigo do municipio sem o check digit
(`350010` em vez de `3500105` = Adamantina). Nao e o codigo oficial do IBGE,
entao nao junta com TSE, CNES, SIH nem com nenhuma base externa. O digito
cortado esta em `setores.cd_mun` (`CD_MUN` do Censo), que ja e de 7 digitos.

O prefixo de 6 digitos e 1:1 com o de 7 (645 municipios de SP), entao o
backfill e deterministico; a migration confere isso antes de escrever.

Revision ID: e2a7c94d18f6
Revises: c8f4d2a91b37
Create Date: 2026-09-29 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2a7c94d18f6"
down_revision: str | None = "c8f4d2a91b37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PREFIXES_AMBIGUOS = """
    SELECT left(cod_mun_ibge, 6) AS curto, count(DISTINCT cod_mun_ibge) AS n
    FROM setores
    WHERE length(cod_mun_ibge) = 7
    GROUP BY 1
    HAVING count(DISTINCT cod_mun_ibge) > 1
"""


def upgrade() -> None:
    bind = op.get_bind()

    conflitos = bind.execute(sa.text(_PREFIXES_AMBIGUOS)).fetchall()
    if conflitos:
        detalhe = ", ".join(f"{linha.curto}->{linha.n}" for linha in conflitos[:5])
        raise RuntimeError(
            "Prefixo de 6 digitos aponta para mais de um municipio de 7 "
            f"({detalhe}); backfill abortado para nao fundir municipios."
        )

    # Alargar antes de escrever: o dado ja cabe (6 -> 7), mas a coluna nao.
    op.execute("ALTER TABLE municipios ALTER COLUMN cod_mun_ibge TYPE varchar(7)")
    op.execute("ALTER TABLE setores ALTER COLUMN cod_mun_ibge TYPE varchar(7)")

    # Os setores ja trazem o codigo completo em `cd_mun`.
    op.execute(
        """
        UPDATE setores
        SET cod_mun_ibge = cd_mun
        WHERE length(cd_mun) = 7
          AND cod_mun_ibge IS DISTINCT FROM cd_mun
        """
    )

    # `municipios` nao tem o digito; o pega emprestado dos setores.
    op.execute(
        """
        UPDATE municipios m
        SET cod_mun_ibge = s.novo
        FROM (
            SELECT left(cod_mun_ibge, 6) AS curto,
                   min(cod_mun_ibge) AS novo
            FROM setores
            WHERE length(cod_mun_ibge) = 7
            GROUP BY 1
        ) s
        WHERE m.cod_mun_ibge = s.curto
          AND length(s.novo) = 7
        """
    )


def downgrade() -> None:
    op.execute("UPDATE setores SET cod_mun_ibge = left(cod_mun_ibge, 6)")
    op.execute("UPDATE municipios SET cod_mun_ibge = left(cod_mun_ibge, 6)")
    op.execute("ALTER TABLE setores ALTER COLUMN cod_mun_ibge TYPE varchar(6)")
    op.execute("ALTER TABLE municipios ALTER COLUMN cod_mun_ibge TYPE varchar(6)")
