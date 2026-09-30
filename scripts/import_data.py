from pathlib import Path

import typer

from src.config import PARQUET_CNES, PARQUET_MUNICIPIOS, PARQUET_SETORES
from src.database import SessionLocal
from src.services.data import (
    atualizar_centroides,
    atualizar_codigos_ibge,
    importar_cnes,
    importar_municipios,
    importar_setores,
)

app = typer.Typer(help="Importa dados dos parquets para o PostGIS.")


@app.command()
def importar(
    tipo: str = typer.Argument("todos", help="setores, municipios, cnes ou todos"),
    caminho: str = typer.Option(None, help="Caminho customizado para o parquet"),
    limite: int = typer.Option(None, help="Limitar número de registros (para testes)"),
    force: bool = typer.Option(False, "--force", "-f", help="Rebaixar dados antes de importar"),
):
    if force:
        from scripts.download_data import download_todos

        download_todos(force=True)

    session = SessionLocal()
    try:
        if tipo in ("municipios", "todos"):
            path = Path(caminho) if caminho and tipo == "municipios" else PARQUET_MUNICIPIOS
            if path.exists():
                n = importar_municipios(path, session)
                print(f"  Municipios: {n} registros importados")
            else:
                print(f"  Arquivo não encontrado: {path}")

        if tipo in ("setores", "todos"):
            path = Path(caminho) if caminho and tipo == "setores" else PARQUET_SETORES
            if path.exists():
                n = importar_setores(path, session, limite=limite)
                print(f"  Setores: {n} registros importados")
            else:
                print(f"  Arquivo não encontrado: {path}")

        if tipo in ("cnes", "todos"):
            path = Path(caminho) if caminho and tipo == "cnes" else PARQUET_CNES
            if path.exists():
                n = importar_cnes(path, session)
                print(f"  CNES: {n} registros importados")
            else:
                print(f"  Arquivo não encontrado: {path}")

        if tipo in ("municipios", "setores", "todos"):
            # O parquet de municípios traz `cod_mun_ibge` com 6 dígitos; o 7º
            # (check digit do IBGE) só existe nos setores (`CD_MUN`). Sem isso
            # um banco recém-criado fica com `350010` e nada junta com base
            # externa — e `atualizar_centroides` logo abaixo não casa as tabelas.
            n_setores, n_municipios = atualizar_codigos_ibge(session)
            print(f"  Códigos IBGE: {n_setores} setores, {n_municipios} municípios corrigidos")
            # Centroide é calculado a partir dos setores — precisa rodar depois
            # do import, senão `buscar_setores_proximos` cai no subSELECT que
            # faz ST_Centroid(ST_Collect(...)) a cada chamada.
            n = atualizar_centroides(session)
            print(f"  Centroides: {n} municípios atualizados")
    finally:
        session.close()


@app.command()
def download(force: bool = typer.Option(False, "--force", "-f")):
    from scripts.download_data import download_todos

    download_todos(force=force)


if __name__ == "__main__":
    app()
