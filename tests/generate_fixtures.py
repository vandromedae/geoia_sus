from pathlib import Path

import geopandas as gpd
import pandas as pd

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
PARQUET_DIR = Path(__file__).parent.parent / "data" / "raw"


def _mapa_ibge7() -> dict[str, str]:
    """6 dígitos (o que o parquet de municípios traz) -> 7 (o oficial do IBGE).

    O check digit cortado só existe em `CD_MUN`, do parquet de setores.
    """
    from src.config import PARQUET_SETORES

    if not PARQUET_SETORES.exists():
        return {}
    df = pd.read_parquet(PARQUET_SETORES, columns=["CD_MUN", "cod_mun_ibge"])
    return dict(zip(df["cod_mun_ibge"].astype(str), df["CD_MUN"].astype(str)))


def generate_fixtures():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # Municipios: pegar 10 municípios de SP
    mun_path = PARQUET_DIR / "base_municipal_densidade_medica.parquet"
    if not mun_path.exists():
        from src.config import PARQUET_MUNICIPIOS

        mun_path = PARQUET_MUNICIPIOS
    if mun_path.exists():
        df = pd.read_parquet(mun_path)
        df_fixture = df.head(10).copy()
        mapa = _mapa_ibge7()
        df_fixture["cod_mun_ibge"] = (
            df_fixture["cod_mun_ibge"].astype(str).map(lambda c: mapa.get(c, c))
        )
        df_fixture.to_parquet(FIXTURES_DIR / "municipios.parquet", index=False)
        print(f"Municipios fixture: {len(df_fixture)} registros")

    # Setores: pegar ~100 setores (2-3 municípios) — preservar geo metadata.
    # `cod_mun_ibge` fica com 6 dígitos de propósito: é o que a release real
    # publica, e exercita o caminho de `CD_MUN` em `importar_setores`.
    set_path = PARQUET_DIR / "setores_com_acessibilidade_real.parquet"
    if not set_path.exists():
        from src.config import PARQUET_SETORES

        set_path = PARQUET_SETORES
    if set_path.exists():
        gdf = gpd.read_parquet(set_path)
        cod_muns = gdf["cod_mun_ibge"].unique()[:3]
        gdf_fixture = gdf[gdf["cod_mun_ibge"].isin(cod_muns)].head(100)
        gdf_fixture.to_parquet(FIXTURES_DIR / "setores.parquet", index=False)
        print(f"Setores fixture: {len(gdf_fixture)} registros (municípios: {cod_muns.tolist()})")

    # CNES: pegar 20 estabelecimentos
    cnes_path = PARQUET_DIR / "cnes_agregados.parquet"
    if cnes_path.exists():
        df = pd.read_parquet(cnes_path)
        df_fixture = df.head(20)
        df_fixture.to_parquet(FIXTURES_DIR / "cnes.parquet", index=False)
        print(f"CNES fixture: {len(df_fixture)} registros")

    print(f"Fixtures salvos em {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_fixtures()
