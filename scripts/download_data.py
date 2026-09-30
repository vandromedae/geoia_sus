import hashlib
import os
import sys
from pathlib import Path

import httpx

from src.config import DATA_DIR, DATA_RELEASE_URL, RELEASE_ASSETS

# SHA256 dos assets da release v0.1.0 (a release não publica arquivo de
# checksum, então o pin fica aqui). Serve para detectar arquivo local
# truncado/corrompido — não para travar a release.
CHECKSUMS_CONHECIDOS = {
    "base_municipal_densidade_medica.parquet": (
        "39909c7170793478227960a6c2c47dca25f4833cf3449dfc509e15f777fb9556"
    ),
    "cnes_agregados.parquet": ("e53ad8b841e794594417d2bfb6c5c276541f1f09db85445323bf5ea085a7c5a9"),
    "setores_com_acessibilidade_real.parquet": (
        "bd97b0308cdb57222e056d906ec1d4b2b51ffcdd819205f60335c5e596bc4a3f"
    ),
}


def sha256_de(caminho: Path) -> str:
    digesto = hashlib.sha256()
    with open(caminho, "rb") as f:
        for pedaco in iter(lambda: f.read(1024 * 1024), b""):
            digesto.update(pedaco)
    return digesto.hexdigest()


def conferir_checksum(caminho: Path, filename: str) -> str:
    """Confere o SHA256 e devolve o hash real.

    Aviso, e não exceção, em divergência: `DATA_RELEASE_URL` aponta para
    `releases/latest`, então um pin velho é esperado quando a release muda.
    """
    atual = sha256_de(caminho)
    esperado = CHECKSUMS_CONHECIDOS.get(filename)
    if esperado is None:
        print(f"    sem hash conhecido para {filename}; conferência pulada")
    elif atual == esperado:
        print(f"    SHA256 ok ({filename})")
    else:
        print(
            f"    AVISO: SHA256 de {filename} diverge do hash conhecido.\n"
            f"      esperado {esperado}\n"
            f"      obtido   {atual}\n"
            f"      Se a release foi atualizada, atualize "
            f"CHECKSUMS_CONHECIDOS em scripts/download_data.py."
        )
    return atual


def download_parquet(nome: str, force: bool = False) -> Path:
    filename = RELEASE_ASSETS.get(nome)
    if not filename:
        raise ValueError(f"Asset desconhecido: {nome}. Disponíveis: {list(RELEASE_ASSETS.keys())}")

    dest = DATA_DIR / filename
    if dest.exists() and not force:
        conferir_checksum(dest, filename)
        print(f"  {filename} já existe, pulando. Use --force para rebaixar.")
        return dest

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    url = f"{DATA_RELEASE_URL}/{filename}"
    print(f"  Baixando {filename}...")

    # `.tmp` + rename atômico: um download interrompido nunca deixa parquet
    # pela metade no lugar do definitivo. Antes o destino era aberto direto e
    # o "pulado se já existir" fazia o arquivo truncado virar permanente.
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                f.flush()
                os.fsync(f.fileno())
        os.replace(tmp, dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    conferir_checksum(dest, filename)
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
