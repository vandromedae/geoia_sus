#!/bin/bash
set -euo pipefail

export PYTHONPATH=/app

echo "=== GeoIA_SUS — Inicializando ==="

# Antes era `|| echo "Aviso: ..."` logo após `set -e`: o `||` neutralizava o
# `set -e` e um download/import que falhava de verdade virava só um avisco —
# a API subia com dados faltando ou desatualizados.
echo "[1/4] Baixando dados..."
python scripts/download_data.py

echo "[2/4] Rodando migrations..."
alembic upgrade head

echo "[3/4] Importando dados..."
DATA_EXISTS=$(python -c "
from src.database import SessionLocal
from src.models import Setor
s = SessionLocal()
print(1 if s.query(Setor).first() else 0)
s.close()
" 2>/dev/null || echo 0)
if [ "$DATA_EXISTS" != "1" ] || [ -n "${FORCE_IMPORT:-}" ]; then
  python scripts/import_data.py importar
else
  echo "  Dados já importados — pulando import (FORCE_IMPORT=1 para reimportar)."
fi

echo "[4/4] Iniciando API..."
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000
