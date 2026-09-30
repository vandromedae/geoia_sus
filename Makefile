LINT_ALVOS = src tests frontend scripts alembic

.PHONY: up down up-offline test test-cov lint format db-check clean

up:
	docker compose up -d --build

down:
	docker compose down

up-offline:
	LLM_PROVIDER=ollama OLLAMA_URL=http://ollama:11434 docker compose --profile offline up -d --build

test:
	poetry run pytest -v

test-cov:
	poetry run pytest --cov=src --cov-report=term-missing

lint:
	poetry run ruff check $(LINT_ALVOS)
	poetry run ruff format --check $(LINT_ALVOS)

format:
	poetry run ruff format $(LINT_ALVOS)

# Confere se os models batem com o schema. Precisa do banco no ar (`make up`)
# e das migrations aplicadas (`poetry run alembic upgrade head`).
db-check:
	poetry run alembic check

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache htmlcov .coverage coverage.xml
