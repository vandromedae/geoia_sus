FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock .
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

COPY src/ src/
COPY frontend/ frontend/
COPY scripts/ scripts/
COPY alembic/ alembic/
COPY alembic.ini .

RUN chmod +x scripts/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["scripts/entrypoint.sh"]
