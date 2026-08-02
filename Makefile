.PHONY: up down test lint format clean

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
	poetry run ruff check src tests
	poetry run ruff format --check src tests

format:
	poetry run ruff format src tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache htmlcov .coverage coverage.xml
