import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Importar os models é o que popula `Base.metadata` (alvo do autogenerate).
from src import models as _models  # noqa: F401
from src.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Filtro do autogenerate, usado por `alembic check` (`make db-check`).
#
# Sem ele o comando compara o schema inteiro contra os models e falha por
# ruído que não é drift nosso:
#   * o PostGIS cria ~80 tabelas no mesmo schema (`tiger`, `topology`,
#     `spatial_ref_sys`, `zip_lookup`, …), que aparecem como `remove_table`;
#   * índices e constraints criados por SQL cru em migrations (índices de
#     expressão como `upper(nm_mun)`, GiST do centroide) não estão declarados
#     nos models e saem como `remove_index`/`remove_constraint`.
#
# Consequência: um índice/constraint que exista só no banco não é reportado.
# É de propósito — modelos são a fonte da verdade do que é gerenciado, e o
# resto é infraestrutura do PostGIS ou índices que criamos à mão.
TABELAS_DO_PROJETO = set(Base.metadata.tables)


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "table":
        return name in TABELAS_DO_PROJETO
    if reflected and compare_to is None and type_ in ("index", "constraint"):
        return False
    return True


db_url = os.getenv("DATABASE_URL")
if not db_url:
    # Sem isto `engine_from_config` estourava um `KeyError: 'url'` sem dizer
    # o que faltava.
    raise RuntimeError(
        "DATABASE_URL não definida. Exporte-a antes de rodar o alembic, "
        "ex: DATABASE_URL=postgresql://geoai:geoai_secret@localhost:5432/geoia_sus "
        "alembic upgrade head"
    )
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
