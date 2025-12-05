FROM python:3.13.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.2.1

WORKDIR /app

# Install build dependencies for psycopg2, Pillow, etc.
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry globally
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# Copy dependency manifests first to leverage Docker layer caching
COPY pyproject.toml poetry.lock* /app/

# Install project dependencies (only main/runtime group)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root \
    && rm -rf /root/.cache/pypoetry

# Copy the rest of the application code
COPY . /app

EXPOSE 8000

# Respect Cloud Run's dynamic PORT (defaults to 8000 for local dev)
CMD ["sh", "-c", "python manage.py runserver 0.0.0.0:${PORT:-8000}"]

