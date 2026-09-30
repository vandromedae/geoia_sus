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
- **Testes:** pytest (164 testes; os de integração são pulados se o PostGIS não estiver no ar)
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
GROQ_MODEL=qwen/qwen3.8-27b
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

`make up-offline` já força `LLM_PROVIDER=ollama` e `OLLAMA_URL` como variáveis
de ambiente do Compose — elas têm prioridade sobre o `.env`, **sem alterar o
arquivo**. Para trocar o modelo, ajuste `OLLAMA_MODEL` no `.env`.

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
make up-offline    # Iniciar com Ollama (env vars do shell; não mexe no .env)
make down          # Parar tudo
make test          # Rodar os testes (sem banco: os de integração são pulados)
make lint          # ruff check + format em src, tests, frontend, scripts e alembic
make format        # Formatar código nos mesmos alvos
make db-check      # alembic check: models x schema (precisa do banco no ar)
make clean         # Limpar caches
```

### Instalação local (sem Docker)

Requer Python 3.11+, PostgreSQL + PostGIS e [Poetry](https://python-poetry.org/).

```bash
poetry install
cp .env.example .env   # Editar com suas credenciais
alembic upgrade head
poetry run python -m scripts.download_data
poetry run python -m scripts.import_data importar
poetry run uvicorn src.api.main:app --reload
```

P.S: os scripts usam `python -m` porque precisam da raiz do repositório no
`sys.path` (`python scripts/download_data.py` falharia com `No module named 'src'`).

### Testes

```bash
make test
```

Os testes de integração (`tests/test_spatial.py`, `tests/test_data.py`,
`tests/test_llm.py` e boa parte de `tests/test_api.py`) consultam o PostGIS.
Com o banco no ar (`make up`) o conjunto completo roda; **sem banco eles são
pulados automaticamente** e o restante — roteamento, serialização, ferramentas
com `spatial` mockado, cache, erros do LLM e frontend — roda normal. É o que
faz o `make test` e o CI funcionarem sem Docker.

Para conferir que os models batem com o schema (com o banco no ar):

```bash
make db-check   # poetry run alembic check
```

## Problemas conhecidos

Há algumas inconsistências pontuais nos dados. Porém, a geração desses dados é feita em outro projeto que está em revisão.

- **50 setores** classificados como "Deserto médico" (nível 6) têm `total_medicos_dentro > 0` e `dist_minima_metros` de 5–8,7 km (acima do raio de 5 km) — contradição interna.
- **3 setores** com `dist_minima_metros < 5 km` mas `e2sfca == 0`.
- Categorias 1/2/3 com ~25% dos setores cada — resultado da classificação por quantis (metodologia relativa, não é bug).

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
