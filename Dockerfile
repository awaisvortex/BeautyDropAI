FROM python:3.12-slim

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

# Copy worker entrypoint and make executable
COPY worker_entrypoint.sh /app/
RUN chmod +x /app/worker_entrypoint.sh

EXPOSE 8080

# Use daphne ASGI server for WebSocket support
# Cloud Run sets PORT env variable (defaults to 8080)
CMD ["sh", "-c", "daphne -b 0.0.0.0 -p ${PORT:-8080} config.asgi:application"]
