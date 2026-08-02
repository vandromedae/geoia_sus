# GeoIA_SUS

Consulta em linguagem natural sobre acessibilidade a médicos do SUS no estado de São Paulo — uma plataforma que combina PostGIS, function calling e IA generativa para responder com dados reais.

## Visão Geral

Pergunte em linguagem natural sobre desertos médicos, compare municípios, visualize setores censitários
em mapa interativo e obtenha insights baseados em dados reais do CNES/DATASUS e Censo IBGE.

## Stack técnica

- **API:** FastAPI + Uvicorn
- **LLM:** Groq (Qwen3) ou Ollama (local)
- **Banco:** PostgreSQL + PostGIS
- **Frontend:** Streamlit + Folium
- **Testes:** pytest (42 testes)
- **Migrações:** Alembic

## Instalação e uso

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2

P.S: Após clonar, você encontrará um script de instalação em scripts/ para Debian/Ubuntu

### Clonar

```bash
git clone https://github.com/vandromedae/geoia_sus.git
cd geoia_sus
cp .env.example .env
```
---

### Instalação do docker (Debian/Ubuntu)

```bash
cd scripts
sudo ./install-docker.sh
cd ..
```
---

### Opção 1: Rodar com Groq

1. Obtenha uma chave API gratuita em [console.groq.com/keys](https://console.groq.com/keys)

2. Edite o `.env` :

```env
LLM_PROVIDER=groq
GROQ_API_KEY=sua_chave_aqui
GROQ_MODEL=qwen/qwen3.6-27b
```

3. Inicie:

```bash
make up
```

---

### Opção 2: Rodar com Ollama (local, 100% offline)

O modelo (~5 GB) será baixado automaticamente pelo Ollama na primeira execução.

1. Edite o `.env` com estas 3 linhas:

```env
LLM_PROVIDER=ollama
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=qwen3:8b
```

2. Inicie:

```bash
make up-offline
```

---

### Primeira execução

O script entrypoint.sh do container automaticamente:

1. Baixa os parquetes do GitHub Releases (~105 MB)
2. Roda as migrações do Alembic (PostGIS)
3. Importa municípios e setores censitários
4. Inicia a API com Uvicorn

### URLs de acesso

| Serviço | URL |
|---------|-----|
| API (Swagger) | http://localhost:8000/docs |
| API (ReDoc) | http://localhost:8000/redoc |
| Frontend | http://localhost:8501 |

### Comandos úteis

```bash
make up            # Iniciar com Groq (ou o que estiver no .env)
make up-offline    # Iniciar com Ollama (sobrescreve .env)
make down          # Parar tudo
make test          # Rodar 42 testes
make lint          # Verificar estilo (ruff)
make format        # Formatar código
make clean         # Limpar caches
```

### Instalação local (sem Docker)

Requer Python 3.11+, PostgreSQL + PostGIS e [Poetry](https://python-poetry.org/).

```bash
poetry install
cp .env.example .env   # Editar com suas credenciais
alembic upgrade head
poetry run python scripts/download_data.py
poetry run python scripts/import_data.py
poetry run uvicorn src.api.main:app --reload
```

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

## Citação

Se você utilizar este código em pesquisa acadêmica, por favor cite:

```bibtex
@software{batista_geoia_sus_2026,
  author    = {Batista, Vanessa},
  title     = {GeoIA\_SUS: Assistente de Saúde Geoespacial com IA Generativa},
  url       = {https://github.com/vandromedae/geoia_sus},
  year      = {2026},
  license   = {MIT}
}
```

Ou use o arquivo [CITATION.cff](CITATION.cff).
