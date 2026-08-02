from pathlib import Path

import geopandas as gpd
import pandas as pd

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
PARQUET_DIR = Path(__file__).parent.parent / "data" / "raw"


def generate_fixtures():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # Municipios: pegar 10 municípios de SP
    mun_path = PARQUET_DIR / "base_municipal_densidade_medica.parquet"
    if mun_path.exists():
        df = pd.read_parquet(mun_path)
        df_fixture = df.head(10)
        df_fixture.to_parquet(FIXTURES_DIR / "municipios.parquet", index=False)
        print(f"Municipios fixture: {len(df_fixture)} registros")

    # Setores: pegar ~100 setores (2-3 municípios) — preservar geo metadata
    set_path = PARQUET_DIR / "setores_com_acessibilidade_real.parquet"
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
