import sys
from pathlib import Path

import httpx

from src.config import DATA_DIR, DATA_RELEASE_URL, RELEASE_ASSETS


def download_parquet(nome: str, force: bool = False) -> Path:
    filename = RELEASE_ASSETS.get(nome)
    if not filename:
        raise ValueError(f"Asset desconhecido: {nome}. Disponíveis: {list(RELEASE_ASSETS.keys())}")

    dest = DATA_DIR / filename
    if dest.exists() and not force:
        print(f"  {filename} já existe, pulando. Use --force para rebaixar.")
        return dest

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    url = f"{DATA_RELEASE_URL}/{filename}"
    print(f"  Baixando {filename}...")

    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=8192):
                f.write(chunk)

    print(f"  Salvo em {dest}")
    return dest


def download_todos(force: bool = False) -> list[Path]:
    print("Baixando dados do GitHub Releases...")
    paths = []
    for nome in RELEASE_ASSETS:
        paths.append(download_parquet(nome, force=force))
    print("Concluído.")
    return paths


if __name__ == "__main__":
    force = "--force" in sys.argv
    download_todos(force=force)
